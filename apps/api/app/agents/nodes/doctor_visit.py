"""Doctor Visit node reuses the audited Phase 12 brief service."""

from sqlalchemy.orm import Session

from app.agents.state import DrRobotState
from app.doctor_visit.service import DoctorVisitService


def doctor_visit_node(db: Session, service: DoctorVisitService):
    def run(state: DrRobotState) -> dict:
        brief = service.generate(db, state["profile_id"], include_llm_rewrite=False)
        return {
            "structured_context": {
                "kind": "doctor_visit",
                "brief": brief.model_dump(mode="json"),
            },
            "draft_response": brief.overview,
            "sources": [
                {
                    "source_type": item.evidence.source_type.value,
                    "label": item.evidence.source_label,
                    "evidence_path": item.evidence.evidence_path,
                    "entity_type": item.evidence.entity_type.value,
                    "entity_id": item.evidence.entity_id,
                }
                for item in [*brief.known_history, *brief.medications, *brief.recent_labs]
            ],
            "actions_taken": ["doctor_visit_brief_generated"],
            "nodes_run": ["doctor_visit"],
        }

    return run
