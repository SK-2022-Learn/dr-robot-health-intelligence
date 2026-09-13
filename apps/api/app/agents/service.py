"""Request-scoped graph execution and privacy-safe observability."""

import logging
from time import monotonic
from typing import Annotated
from uuid import uuid4

from fastapi import Depends
from sqlalchemy.orm import Session

from app.agents.graph import AgentServices, build_agent_graph
from app.agents.schemas import AgentIntent, AgentSource, AskRequest, AskResponse
from app.analytics.service import AnalyticsService
from app.chat.service import ChatService
from app.config import Settings, get_settings
from app.core.errors import ApiError
from app.database.models import HealthProfile
from app.doctor_visit.service import DoctorVisitService
from app.embeddings.base import EmbeddingProvider
from app.embeddings.factory import get_embedding_provider
from app.family.service import FamilyService
from app.llm.base import LLMProvider
from app.llm.factory import get_llm_provider
from app.retrieval.service import RetrievalService
from app.safety.enums import SafetyCategory
from app.safety.service import SafetyService
from app.timeline.evidence import EvidenceService
from app.timeline.service import TimelineService
from app.vectorstore.base import VectorStoreProvider
from app.vectorstore.factory import get_vector_store_provider

logger = logging.getLogger("dr_robot.agent")


class AgentService:
    def __init__(
        self,
        llm: LLMProvider,
        embeddings: EmbeddingProvider,
        vector_store: VectorStoreProvider,
        *,
        settings: Settings | None = None,
        services: AgentServices | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        safety = SafetyService()
        timeline = TimelineService()
        analytics = AnalyticsService(llm, settings=self.settings)
        self.services = services or AgentServices(
            safety=safety,
            chat=ChatService(llm, safety=safety),
            retrieval=RetrievalService(vector_store, embeddings),
            timeline=timeline,
            analytics=analytics,
            family=FamilyService(),
            evidence=EvidenceService(),
            doctor_visit=DoctorVisitService(
                llm, timeline=timeline, analytics=analytics, safety=safety
            ),
            llm=llm,
        )

    def health_check(self, db: Session) -> bool:
        try:
            build_agent_graph(db, self.services)
        except Exception:
            logger.exception("Agent graph compilation failed")
            return False
        return True

    def ask(self, db: Session, profile_id: str, request: AskRequest) -> AskResponse:
        profile = db.get(HealthProfile, profile_id)
        if profile is None:
            raise ApiError(
                status_code=404,
                code="PROFILE_NOT_FOUND",
                message="Health profile was not found.",
            )
        request_id = str(uuid4())
        started = monotonic()
        status = "ok"
        try:
            graph = build_agent_graph(db, self.services)
            graph.step_timeout = self.settings.agent_timeout_seconds
            state = graph.invoke(
                {
                    "request_id": request_id,
                    "profile_id": profile_id,
                    "user_id": profile.owner_user_id,
                    "conversation_id": request.conversation_id,
                    "user_query": request.message,
                    "warnings": [],
                    "sources": [],
                    "actions_taken": [],
                    "nodes_run": [],
                    "clarification_required": False,
                },
                config={"recursion_limit": 20},
            )
        except Exception:
            status = "error"
            raise
        finally:
            logger.info(
                "Agent request completed",
                extra={
                    "request_id": request_id,
                    "agent_intent": locals().get("state", {}).get("intent", "UNROUTED"),
                    "agent_nodes": locals().get("state", {}).get("nodes_run", []),
                    "duration_ms": round((monotonic() - started) * 1000, 2),
                    "result_status": status,
                    "safety_decision": getattr(
                        locals().get("state", {}).get("safety_result"), "decision", None
                    ),
                },
            )

        safety = state.get("safety_result")
        intent = state.get("intent")
        if intent is None:
            intent = (
                AgentIntent.UNSUPPORTED_MEDICAL_ACTION
                if safety and safety.category != SafetyCategory.URGENT_SYMPTOM
                else AgentIntent.UNKNOWN
            )
        structured = (
            state.get("analytics_context")
            or state.get("family_context")
            or state.get("timeline_context")
            or state.get("structured_context")
            or state.get("retrieval_context")
        )
        evidence = state.get("evidence_context", [])
        return AskResponse(
            request_id=request_id,
            intent=intent,
            answer=state.get("final_response") or state.get("draft_response", ""),
            conversation_id=state.get("conversation_id"),
            pending_id=state.get("pending_id"),
            clarification_required=state.get("clarification_required", False),
            sources=[AgentSource.model_validate(item) for item in state.get("sources", [])],
            evidence=evidence,
            safety=safety,
            warnings=list(dict.fromkeys(state.get("warnings", []))),
            actions=list(dict.fromkeys(state.get("actions_taken", []))),
            structured_result=structured,
            nodes_run=state.get("nodes_run") if request.include_trace else None,
        )


def get_agent_service(
    llm: Annotated[LLMProvider, Depends(get_llm_provider)],
    embeddings: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
    vector_store: Annotated[VectorStoreProvider, Depends(get_vector_store_provider)],
) -> AgentService:
    return AgentService(llm, embeddings, vector_store)
