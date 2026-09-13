"""Timeline queries delegate ordering and provenance to TimelineService."""

from sqlalchemy.orm import Session

from app.agents.nodes.memory import item_source, relevant_items
from app.agents.state import DrRobotState
from app.database.enums import VerificationStatus
from app.timeline.service import TimelineService


def timeline_node(db: Session, service: TimelineService):
    def run(state: DrRobotState) -> dict:
        response = service.list(db, state["profile_id"], sort="asc", limit=200)
        trusted = [
            item
            for item in response.items
            if item.verification_status == VerificationStatus.VERIFIED
        ]
        matches = relevant_items(state["user_query"], trusted)
        if matches:
            first = matches[0]
            when = first.occurred_at.date().isoformat() if first.occurred_at else "an unknown date"
            answer = f"{first.title} was first documented on {when}."
        elif trusted:
            matches = trusted[:8]
            answer = f"I found {len(trusted)} trusted timeline item(s) for this profile."
        else:
            answer = "No trusted timeline items are recorded for this profile."
        return {
            "timeline_context": {
                "profile_id": state["profile_id"],
                "items": [item.model_dump(mode="json") for item in matches],
            },
            "draft_response": answer,
            "sources": [item_source(state["profile_id"], item) for item in matches],
            "actions_taken": ["timeline_read"],
            "nodes_run": ["timeline"],
        }

    return run
