"""Evidence resolution for trusted records and computed analytics."""

from sqlalchemy.orm import Session

from app.agents.nodes.memory import item_source, relevant_items
from app.agents.state import DrRobotState
from app.core.errors import ApiError
from app.database.enums import VerificationStatus
from app.timeline.evidence import EvidenceService
from app.timeline.service import TimelineService


def evidence_node(db: Session, timeline: TimelineService, evidence: EvidenceService):
    def run(state: DrRobotState) -> dict:
        analytics = state.get("analytics_context")
        if analytics:
            points = analytics.get("evidence", [])
            if not points and analytics.get("results"):
                points = [
                    point for result in analytics["results"] for point in result.get("evidence", [])
                ]
            return {
                "evidence_context": points,
                "sources": [
                    {
                        "source_type": point.get("source_type", "DERIVED"),
                        "label": point.get("source_label", "Analytics evidence"),
                        "evidence_path": point.get("evidence_path"),
                        "entity_type": "observation",
                        "entity_id": point.get("observation_id"),
                    }
                    for point in points
                ],
                "actions_taken": ["analytics_evidence_attached"],
                "nodes_run": ["evidence"],
            }

        response = timeline.list(db, state["profile_id"], sort="desc", limit=200)
        trusted = [
            item
            for item in response.items
            if item.verification_status == VerificationStatus.VERIFIED and item.has_evidence
        ]
        matches = relevant_items(state["user_query"], trusted)
        resolved = []
        sources = []
        for item in matches[:3]:
            try:
                detail = evidence.resolve(db, state["profile_id"], item.entity_type, item.entity_id)
            except ApiError:
                continue
            resolved.append(detail.model_dump(mode="json"))
            sources.append(item_source(state["profile_id"], item))
        if resolved:
            first = resolved[0]
            source = first["source"]
            source_label = source.get("filename") or source.get("label") or source.get("type")
            answer = f"That value is supported by {source_label}."
            if source.get("page_number"):
                answer += f" See page {source['page_number']}."
        else:
            answer = "I couldn't resolve a trusted source for that statement."
        return {
            "evidence_context": resolved,
            "draft_response": answer,
            "sources": sources,
            "actions_taken": ["evidence_resolved"],
            "nodes_run": ["evidence"],
        }

    return run
