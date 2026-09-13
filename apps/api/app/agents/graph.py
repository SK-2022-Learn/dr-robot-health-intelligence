"""LangGraph topology; nodes orchestrate services but contain no domain rules."""

from dataclasses import dataclass
from typing import Literal

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.agents.nodes.analytics import analytics_node
from app.agents.nodes.daily_log import daily_log_node
from app.agents.nodes.doctor_visit import doctor_visit_node
from app.agents.nodes.evidence import evidence_node
from app.agents.nodes.explanation import explanation_node
from app.agents.nodes.family import family_node
from app.agents.nodes.memory import memory_node
from app.agents.nodes.retrieval import retrieval_node
from app.agents.nodes.safety import safety_post_node, safety_pre_node
from app.agents.nodes.timeline import timeline_node
from app.agents.router import route_intent
from app.agents.schemas import AgentIntent
from app.agents.state import DrRobotState
from app.analytics.service import AnalyticsService
from app.chat.service import ChatService
from app.doctor_visit.service import DoctorVisitService
from app.family.service import FamilyService
from app.llm.base import LLMProvider
from app.retrieval.service import RetrievalService
from app.safety.enums import SafetyDecision
from app.safety.service import SafetyService
from app.timeline.evidence import EvidenceService
from app.timeline.service import TimelineService


@dataclass(frozen=True)
class AgentServices:
    safety: SafetyService
    chat: ChatService
    retrieval: RetrievalService
    timeline: TimelineService
    analytics: AnalyticsService
    family: FamilyService
    evidence: EvidenceService
    doctor_visit: DoctorVisitService
    llm: LLMProvider


def _router_node(state: DrRobotState) -> dict:
    return {"intent": route_intent(state["user_query"]), "nodes_run": ["router"]}


def _after_pre(state: DrRobotState) -> Literal["continue", "stop"]:
    if state["safety_result"].decision in {SafetyDecision.BLOCK, SafetyDecision.ESCALATE}:
        return "stop"
    return "continue"


def _branch(state: DrRobotState) -> str:
    return state["intent"].value


def build_agent_graph(db: Session, services: AgentServices):
    builder = StateGraph(DrRobotState)
    builder.add_node("safety_pre", safety_pre_node(db, services.safety))
    builder.add_node("router", _router_node)
    builder.add_node("daily_log", daily_log_node(db, services.chat))
    builder.add_node("memory", memory_node(db, services.timeline))
    builder.add_node("retrieval", retrieval_node(db, services.retrieval))
    builder.add_node("timeline", timeline_node(db, services.timeline))
    builder.add_node("analytics", analytics_node(db, services.analytics))
    builder.add_node("family", family_node(db, services.family))
    builder.add_node("evidence", evidence_node(db, services.timeline, services.evidence))
    builder.add_node("doctor_visit", doctor_visit_node(db, services.doctor_visit))
    builder.add_node("explanation", explanation_node(services.llm))
    builder.add_node("safety_post", safety_post_node(db, services.safety))

    builder.add_edge(START, "safety_pre")
    builder.add_conditional_edges("safety_pre", _after_pre, {"continue": "router", "stop": END})
    builder.add_conditional_edges(
        "router",
        _branch,
        {
            AgentIntent.DAILY_LOG.value: "daily_log",
            AgentIntent.RECORD_LOOKUP.value: "memory",
            AgentIntent.TIMELINE_QUERY.value: "timeline",
            AgentIntent.EVIDENCE_QUERY.value: "evidence",
            AgentIntent.ANALYTICS_QUERY.value: "analytics",
            AgentIntent.FAMILY_QUERY.value: "family",
            AgentIntent.DOCTOR_VISIT.value: "doctor_visit",
            AgentIntent.GENERAL_HEALTH_INFORMATION.value: "explanation",
            AgentIntent.UNSUPPORTED_MEDICAL_ACTION.value: "explanation",
            AgentIntent.UNKNOWN.value: "explanation",
        },
    )
    builder.add_edge("memory", "retrieval")
    builder.add_edge("retrieval", "explanation")
    builder.add_edge("timeline", "explanation")
    builder.add_edge("analytics", "evidence")
    builder.add_edge("evidence", "explanation")
    builder.add_edge("family", "explanation")
    builder.add_edge("doctor_visit", "explanation")
    builder.add_edge("daily_log", "explanation")
    builder.add_edge("explanation", "safety_post")
    builder.add_edge("safety_post", END)
    return builder.compile()


def graph_runtime_available() -> bool:
    """Compile a dependency-free probe graph for health reporting."""

    try:
        builder = StateGraph(DrRobotState)
        builder.add_node("probe", lambda _state: {"nodes_run": ["probe"]})
        builder.add_edge(START, "probe")
        builder.add_edge("probe", END)
        builder.compile()
    except Exception:
        return False
    return True
