"""Permission-authoritative family intelligence node."""

from sqlalchemy.orm import Session

from app.agents.state import DrRobotState
from app.family.service import FamilyService


def family_node(db: Session, service: FamilyService):
    def run(state: DrRobotState) -> dict:
        result = service.pattern_results(db, state["profile_id"], state["user_id"])
        if result.patterns:
            answer = " ".join(pattern.statement for pattern in result.patterns[:3])
        else:
            answer = (
                "No repeated family conditions are documented across profiles you are permitted "
                "to include."
            )
        data = result.model_dump(mode="json")
        sources = [
            {
                "source_type": "FAMILY_PERMISSIONED",
                "label": pattern.condition_name,
                "evidence_path": evidence.evidence_path,
                "entity_type": "health_event",
                "entity_id": evidence.health_event_id,
            }
            for pattern in result.patterns
            for contributor in pattern.contributing_profiles
            for evidence in contributor.evidence
        ]
        return {
            "family_context": data,
            "draft_response": answer,
            "sources": sources,
            "actions_taken": ["family_permission_check", "family_pattern_read"],
            "nodes_run": ["family"],
        }

    return run
