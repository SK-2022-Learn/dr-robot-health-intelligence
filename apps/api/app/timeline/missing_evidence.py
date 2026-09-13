"""Deterministic structural-gap detection without clinical inference."""

from sqlalchemy.orm import Session

from app.database.enums import VerificationStatus
from app.timeline.schemas import (
    MissingEvidenceGap,
    MissingEvidenceResponse,
    MissingEvidenceType,
    TimelineEntityType,
)
from app.timeline.service import TimelineService


class MissingEvidenceService:
    def __init__(self, timeline: TimelineService | None = None) -> None:
        self.timeline = timeline or TimelineService()

    def list(self, db: Session, profile_id: str) -> MissingEvidenceResponse:
        timeline = self.timeline.list(db, profile_id, limit=10_000)
        gaps: list[MissingEvidenceGap] = []
        for item in timeline.items:
            if not item.has_evidence:
                gaps.append(
                    MissingEvidenceGap(
                        type=MissingEvidenceType.MISSING_SOURCE,
                        entity_type=item.entity_type,
                        entity_id=item.entity_id,
                        message="No supporting source is linked to this record.",
                    )
                )
            if item.occurred_at is None:
                message = (
                    "Medication reconciliation date is unavailable."
                    if item.entity_type == TimelineEntityType.MEDICATION
                    else "Date is unavailable for this record."
                )
                gaps.append(
                    MissingEvidenceGap(
                        type=MissingEvidenceType.MISSING_DATE,
                        entity_type=item.entity_type,
                        entity_id=item.entity_id,
                        message=message,
                    )
                )
            if item.verification_status != VerificationStatus.VERIFIED:
                gaps.append(
                    MissingEvidenceGap(
                        type=MissingEvidenceType.UNVERIFIED_FACT,
                        entity_type=item.entity_type,
                        entity_id=item.entity_id,
                        message="Verification is still needed for this record.",
                    )
                )
        return MissingEvidenceResponse(profile_id=profile_id, gaps=gaps)
