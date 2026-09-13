"""Permission-filtered evidence references for family condition records."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import EvidenceLink, HealthEvent
from app.family.schemas import FamilyEvidenceReference


class FamilyEvidenceService:
    def for_condition_event(
        self, db: Session, event: HealthEvent, *, include_details: bool
    ) -> tuple[int, list[FamilyEvidenceReference]]:
        link_count = int(
            db.scalar(
                select(func.count())
                .select_from(EvidenceLink)
                .where(EvidenceLink.health_event_id == event.id)
            )
            or 0
        )
        source_count = max(link_count, 1 if event.source_document_id else 0)
        if not include_details:
            return source_count, []
        return source_count, [
            FamilyEvidenceReference(
                health_event_id=event.id,
                evidence_path=(
                    f"/api/v1/profiles/{event.profile_id}/evidence/health_event/{event.id}"
                ),
                source_count=source_count,
            )
        ]
