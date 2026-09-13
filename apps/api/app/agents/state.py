"""Explicit, inspectable graph state without hidden reasoning or prompts."""

import operator
from typing import Annotated, Any, TypedDict

from app.agents.schemas import AgentIntent
from app.safety.schemas import SafetyResult


class DrRobotState(TypedDict, total=False):
    request_id: str
    profile_id: str
    user_id: str
    conversation_id: str | None
    user_query: str
    intent: AgentIntent
    safety_result: SafetyResult
    structured_context: dict[str, Any]
    timeline_context: dict[str, Any]
    retrieval_context: dict[str, Any]
    analytics_context: dict[str, Any]
    family_context: dict[str, Any]
    evidence_context: list[dict[str, Any]]
    draft_response: str
    final_response: str
    pending_id: str | None
    clarification_required: bool
    warnings: Annotated[list[str], operator.add]
    sources: Annotated[list[dict[str, Any]], operator.add]
    actions_taken: Annotated[list[str], operator.add]
    nodes_run: Annotated[list[str], operator.add]
