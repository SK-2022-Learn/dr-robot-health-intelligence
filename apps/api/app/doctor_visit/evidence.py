"""Adapters that retain Phase 8 evidence resolution in Doctor Visit items."""

from sqlalchemy.orm import Session

from app.doctor_visit.schemas import EvidenceSummaryItem, VisitEvidenceReference
from app.timeline.evidence import EvidenceService
from app.timeline.schemas import (
    ChatEvidenceSource,
    DocumentEvidenceSource,
    TimelineItem,
    TimelineSourceType,
)


class DoctorVisitEvidenceService:
    def __init__(self, evidence: EvidenceService | None = None) -> None:
        self.evidence = evidence or EvidenceService()

    def reference(self, db: Session, profile_id: str, item: TimelineItem) -> VisitEvidenceReference:
        resolved = self.evidence.resolve(db, profile_id, item.entity_type, item.entity_id)
        if isinstance(resolved.source, DocumentEvidenceSource):
            page = f", page {resolved.source.page_number}" if resolved.source.page_number else ""
            label = f"{resolved.source.filename}{page}"
        elif isinstance(resolved.source, ChatEvidenceSource):
            label = resolved.source.label
        elif resolved.source_type == TimelineSourceType.DERIVED:
            label = "Derived from trusted structured records"
        else:
            label = "No linked source evidence"
        return VisitEvidenceReference(
            entity_type=item.entity_type,
            entity_id=item.entity_id,
            source_type=resolved.source_type,
            source_label=label,
            provenance=resolved.provenance,
            verification_status=resolved.verification_status,
            has_evidence=item.has_evidence,
            evidence_path=(
                f"/api/v1/profiles/{profile_id}/evidence/{item.entity_type.value}/{item.entity_id}"
            ),
        )


def evidence_summary(items: list[TimelineItem], missing_count: int) -> list[EvidenceSummaryItem]:
    verified = [item for item in items if item.verification_status.value == "VERIFIED"]
    return [
        EvidenceSummaryItem(
            key="VERIFIED_DOCUMENT_SOURCES",
            label="Verified document sources",
            count=len(
                {
                    item.source_document_id
                    for item in verified
                    if item.source_type == TimelineSourceType.DOCUMENT
                    and item.source_document_id is not None
                }
            ),
        ),
        EvidenceSummaryItem(
            key="USER_REPORTED_ITEMS",
            label="User-reported items",
            count=sum(
                item.provenance.value in {"USER_REPORTED", "USER_CORRECTED"} for item in verified
            ),
        ),
        EvidenceSummaryItem(
            key="MISSING_EVIDENCE_ITEMS",
            label="Missing evidence items",
            count=missing_count,
        ),
        EvidenceSummaryItem(
            key="UNVERIFIED_ITEMS",
            label="Unverified items excluded",
            count=sum(item.verification_status.value != "VERIFIED" for item in items),
        ),
    ]
