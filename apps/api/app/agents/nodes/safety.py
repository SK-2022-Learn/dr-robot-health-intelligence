"""Mandatory pre- and post-generation safety gates."""

from sqlalchemy.orm import Session

from app.agents.state import DrRobotState
from app.safety.enums import SafetyDecision
from app.safety.schemas import SafetyInput
from app.safety.service import SafetyService


def safety_pre_node(db: Session, service: SafetyService):
    def run(state: DrRobotState) -> dict:
        result = service.pre_check(
            SafetyInput(
                user_text=state["user_query"],
                profile_id=state["profile_id"],
                context_type="AGENT_GRAPH",
                source="ASK_DR_ROBOT",
            )
        )
        service.audit_result(
            db,
            result,
            entity_id=state["request_id"],
            profile_id=state["profile_id"],
            actor_user_id=state["user_id"],
        )
        db.commit()
        update: dict = {"safety_result": result, "nodes_run": ["safety_pre"]}
        if result.decision in {SafetyDecision.BLOCK, SafetyDecision.ESCALATE}:
            update.update(
                draft_response=result.safe_response_override or result.message,
                final_response=result.safe_response_override or result.message,
                warnings=[result.message],
                actions_taken=["safety_short_circuit"],
            )
        return update

    return run


def safety_post_node(db: Session, service: SafetyService):
    def run(state: DrRobotState) -> dict:
        draft = state.get("draft_response", "")
        result = service.post_check(
            SafetyInput(
                user_text=state["user_query"],
                draft_response=draft,
                intent=state.get("intent", "UNKNOWN"),
                profile_id=state["profile_id"],
                context_type="AGENT_GRAPH",
                source="ASK_DR_ROBOT",
            )
        )
        service.audit_result(
            db,
            result,
            entity_id=state["request_id"],
            profile_id=state["profile_id"],
            actor_user_id=state["user_id"],
        )
        db.commit()
        final = result.safe_response_override or draft
        update: dict = {
            "safety_result": result,
            "final_response": final,
            "nodes_run": ["safety_post"],
        }
        if result.decision != SafetyDecision.ALLOW:
            update["warnings"] = [result.message]
        return update

    return run
