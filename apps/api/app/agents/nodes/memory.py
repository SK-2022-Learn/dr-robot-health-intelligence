"""Trusted-memory lookup built on the authoritative timeline projection."""

import re

from sqlalchemy.orm import Session

from app.agents.state import DrRobotState
from app.database.enums import VerificationStatus
from app.timeline.service import TimelineService

_WORDS = re.compile(r"[a-z0-9.]+")
_IGNORED = {"the", "my", "a", "an", "is", "was", "do", "does", "what", "latest", "record"}


def relevant_items(query: str, items: list, *, limit: int = 8) -> list:
    terms = set(_WORDS.findall(query.casefold())) - _IGNORED
    if "a1c" in terms:
        terms.add("hba1c")
    ranked = []
    for item in items:
        haystack = f"{item.title} {item.description or ''}".casefold()
        score = sum(1 for term in terms if term in haystack)
        if score:
            ranked.append((score, item))
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in ranked[:limit]]


def item_source(profile_id: str, item) -> dict:
    return {
        "source_type": item.source_type.value,
        "label": item.title,
        "evidence_path": (
            f"/api/v1/profiles/{profile_id}/evidence/{item.entity_type.value}/{item.entity_id}"
            if item.has_evidence
            else None
        ),
        "entity_type": item.entity_type.value,
        "entity_id": item.entity_id,
        "document_id": item.source_document_id,
    }


def memory_node(db: Session, service: TimelineService):
    def run(state: DrRobotState) -> dict:
        timeline = service.list(db, state["profile_id"], sort="desc", limit=200)
        trusted = [
            item
            for item in timeline.items
            if item.verification_status == VerificationStatus.VERIFIED
        ]
        matches = relevant_items(state["user_query"], trusted)
        generic_lookup = any(
            word in state["user_query"].casefold() for word in ("latest", "record")
        )
        if not matches and generic_lookup:
            matches = trusted[:8]
        if not matches:
            answer = "I couldn't find a matching trusted record for this profile."
        else:
            details = "; ".join(
                f"{item.title}: {item.description or 'recorded'}"
                + (f" on {item.occurred_at.date().isoformat()}" if item.occurred_at else "")
                for item in matches[:3]
            )
            answer = f"The trusted record shows {details}."
        return {
            "structured_context": {
                "kind": "record_lookup",
                "items": [item.model_dump(mode="json") for item in matches],
            },
            "draft_response": answer,
            "sources": [item_source(state["profile_id"], item) for item in matches],
            "actions_taken": ["trusted_memory_read"],
            "nodes_run": ["memory"],
        }

    return run
