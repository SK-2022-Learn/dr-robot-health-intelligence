"""Profile-scoped evidence and correction-history resolution."""

from typing import Any
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.chat.schemas import (
    BloodPressureEntry,
    DailyHealthExtraction,
    GlucoseEntry,
    WeightEntry,
)
from app.core.errors import ApiError
from app.database.enums import ProvenanceType
from app.database.models import (
    AuditLog,
    DocumentPage,
    EvidenceLink,
    ExtractedCandidate,
    HealthEvent,
    Medication,
    Message,
    Observation,
    PendingHealthEntry,
    SourceDocument,
    Symptom,
)
from app.timeline.schemas import (
    ChatEvidenceSource,
    CorrectionHistoryItem,
    DocumentEvidenceSource,
    EvidenceResponse,
    ManualEvidenceSource,
    TimelineEntityType,
    TimelineSourceType,
)

TimelineTarget = HealthEvent | Observation | Medication | Symptom


def format_target_value(target: TimelineTarget) -> str | None:
    if isinstance(target, Observation):
        value = target.value_number if target.value_number is not None else target.value_text
        if value is None:
            return None
        number = f"{value:g}" if isinstance(value, float) else str(value)
        return f"{number} {target.unit}".strip() if target.unit else number
    if isinstance(target, Medication):
        dose = " ".join(part for part in (target.dose, target.dose_unit) if part)
        return " · ".join(part for part in (dose, target.frequency, target.route) if part) or None
    if isinstance(target, Symptom):
        return f"Severity {target.severity}/10" if target.severity is not None else target.notes
    return target.description


def _candidate_value(values: dict[str, Any]) -> str | None:
    raw = values.get("value_number")
    if raw is None:
        raw = values.get("value_text")
    if raw is not None:
        number = f"{raw:g}" if isinstance(raw, float) else str(raw)
        unit = values.get("unit")
        return f"{number} {unit}".strip() if unit else number
    name = values.get("condition_name") or values.get("name")
    if name:
        dose = " ".join(str(part) for part in (values.get("dose"), values.get("dose_unit")) if part)
        return " · ".join(str(part) for part in (name, dose, values.get("frequency")) if part)
    return None


def _pending_values(extraction: DailyHealthExtraction) -> list[str | None]:
    values: list[str | None] = []
    for item in extraction.observations:
        if isinstance(item, BloodPressureEntry):
            values.append(f"{item.systolic}/{item.diastolic} {item.unit}")
        elif isinstance(item, (GlucoseEntry, WeightEntry)):
            values.append(f"{item.value:g} {item.unit or ''}".strip())
    values.extend(f"{item.duration_minutes:g} min" for item in extraction.sleep_entries)
    for item in extraction.activities:
        if item.duration_minutes is not None:
            values.append(f"{item.duration_minutes:g} min")
        elif item.distance is not None:
            values.append(f"{item.distance:g} {item.distance_unit or ''}".strip())
        else:
            values.append(None)
    values.extend(
        f"Severity {item.severity.value.title()}" if item.severity.value != "UNKNOWN" else item.name
        for item in extraction.symptoms
    )
    return values


class EvidenceService:
    def _require_target(
        self,
        db: Session,
        profile_id: str,
        entity_type: TimelineEntityType,
        entity_id: str,
    ) -> TimelineTarget:
        models = {
            TimelineEntityType.HEALTH_EVENT: HealthEvent,
            TimelineEntityType.OBSERVATION: Observation,
            TimelineEntityType.MEDICATION: Medication,
            TimelineEntityType.SYMPTOM: Symptom,
        }
        model = models[entity_type]
        target = db.scalar(
            select(model).where(model.id == entity_id, model.profile_id == profile_id)
        )
        if target is None:
            raise ApiError(
                status_code=404,
                code="TIMELINE_ITEM_NOT_FOUND",
                message="Timeline item was not found for this profile.",
            )
        return target

    @staticmethod
    def _link_for_target(
        db: Session, profile_id: str, entity_type: TimelineEntityType, entity_id: str
    ) -> EvidenceLink | None:
        columns = {
            TimelineEntityType.HEALTH_EVENT: EvidenceLink.health_event_id,
            TimelineEntityType.OBSERVATION: EvidenceLink.observation_id,
            TimelineEntityType.MEDICATION: EvidenceLink.medication_id,
            TimelineEntityType.SYMPTOM: EvidenceLink.symptom_id,
        }
        return db.scalar(
            select(EvidenceLink)
            .join(SourceDocument)
            .where(
                columns[entity_type] == entity_id,
                SourceDocument.profile_id == profile_id,
            )
            .order_by(EvidenceLink.created_at, EvidenceLink.id)
        )

    @staticmethod
    def _document_source(
        db: Session,
        profile_id: str,
        link: EvidenceLink | None,
        direct_document_id: str | None,
    ) -> DocumentEvidenceSource | None:
        document_id = link.source_document_id if link else direct_document_id
        if document_id is None:
            return None
        document = db.scalar(
            select(SourceDocument).where(
                SourceDocument.id == document_id,
                SourceDocument.profile_id == profile_id,
            )
        )
        if document is None:
            return None
        page = None
        if link and link.page_number is not None:
            page = db.scalar(
                select(DocumentPage).where(
                    DocumentPage.document_id == document.id,
                    DocumentPage.page_number == link.page_number,
                )
            )
        query = f"document={quote(document.id)}"
        if link and link.page_number is not None:
            query += f"&page={link.page_number}"
        return DocumentEvidenceSource(
            document_id=document.id,
            filename=document.original_filename,
            document_date=document.document_date,
            page_number=link.page_number if link else None,
            excerpt=link.source_excerpt if link else None,
            page_text=page.text if page else None,
            view_source_path=f"/uploads?{query}",
        )

    @staticmethod
    def _chat_pending(
        db: Session, profile_id: str, source_message_id: str | None
    ) -> tuple[Message, PendingHealthEntry] | None:
        if source_message_id is None:
            return None
        message = db.get(Message, source_message_id)
        if message is None or message.conversation.profile_id != profile_id:
            return None
        pending = db.scalar(
            select(PendingHealthEntry).where(
                PendingHealthEntry.message_id == message.id,
                PendingHealthEntry.profile_id == profile_id,
            )
        )
        return (message, pending) if pending else None

    @staticmethod
    def _chat_original_value(
        pending: PendingHealthEntry, entity_type: TimelineEntityType, entity_id: str
    ) -> str | None:
        manifest = pending.trusted_records or []
        record_type = {
            TimelineEntityType.OBSERVATION: "observations",
            TimelineEntityType.SYMPTOM: "symptoms",
        }.get(entity_type)
        position = next(
            (
                index
                for index, record in enumerate(manifest)
                if record.get("record_type") == record_type and record.get("record_id") == entity_id
            ),
            None,
        )
        if position is None:
            return None
        values = _pending_values(
            DailyHealthExtraction.model_validate(pending.original_structured_data)
        )
        return values[position] if position < len(values) else None

    @staticmethod
    def _candidate_correction(
        db: Session, profile_id: str, entity_type: TimelineEntityType, entity_id: str
    ) -> tuple[ExtractedCandidate, AuditLog] | None:
        record_type = {
            TimelineEntityType.HEALTH_EVENT: "health_events",
            TimelineEntityType.OBSERVATION: "observations",
            TimelineEntityType.MEDICATION: "medications",
            TimelineEntityType.SYMPTOM: "symptoms",
        }[entity_type]
        audits = db.scalars(select(AuditLog).where(AuditLog.action == "CANDIDATE_CORRECTED")).all()
        for audit in audits:
            reference = (audit.after_state or {}).get("trusted_record", {})
            if (
                reference.get("record_type") != record_type
                or reference.get("record_id") != entity_id
            ):
                continue
            candidate = db.get(ExtractedCandidate, audit.entity_id)
            if candidate and candidate.document.profile_id == profile_id:
                return candidate, audit
        return None

    def resolve(
        self,
        db: Session,
        profile_id: str,
        entity_type: TimelineEntityType,
        entity_id: str,
    ) -> EvidenceResponse:
        target = self._require_target(db, profile_id, entity_type, entity_id)
        link = self._link_for_target(db, profile_id, entity_type, entity_id)
        direct_document_id = target.source_document_id if isinstance(target, HealthEvent) else None
        document_source = self._document_source(db, profile_id, link, direct_document_id)
        source_message_id = (
            target.source_message_id if isinstance(target, (Observation, Symptom)) else None
        )
        chat = self._chat_pending(db, profile_id, source_message_id)
        saved_value = format_target_value(target)
        corrections: list[CorrectionHistoryItem] = []

        if document_source is not None:
            source_type = TimelineSourceType.DOCUMENT
            source = document_source
            candidate_correction = self._candidate_correction(
                db, profile_id, entity_type, entity_id
            )
            if candidate_correction:
                candidate, audit = candidate_correction
                corrected_data = (audit.after_state or {}).get("corrected_data", {})
                changed = sorted(
                    key
                    for key, value in corrected_data.items()
                    if key in candidate.structured_data
                    and candidate.structured_data.get(key) != value
                )
                corrections.append(
                    CorrectionHistoryItem(
                        action=audit.action,
                        original_value=_candidate_value(candidate.structured_data),
                        corrected_value=saved_value,
                        changed_fields=changed,
                        corrected_at=audit.created_at,
                        actor=audit.actor.username if audit.actor else None,
                    )
                )
        elif chat is not None:
            message, pending = chat
            source_type = TimelineSourceType.CHAT
            source = ChatEvidenceSource(
                conversation_id=message.conversation_id,
                message_id=message.id,
                message=message.content,
                message_timestamp=message.created_at,
            )
            if pending.was_corrected:
                original = self._chat_original_value(pending, entity_type, entity_id)
                for audit in db.scalars(
                    select(AuditLog)
                    .where(
                        AuditLog.entity_type == "pending_health_entry",
                        AuditLog.entity_id == pending.id,
                        AuditLog.action == "CHAT_ENTRY_CORRECTED",
                    )
                    .order_by(AuditLog.created_at, AuditLog.id)
                ):
                    corrections.append(
                        CorrectionHistoryItem(
                            action=audit.action,
                            original_value=original,
                            corrected_value=saved_value,
                            changed_fields=(audit.after_state or {}).get("changed_fields", []),
                            corrected_at=audit.created_at,
                            actor=audit.actor.username if audit.actor else None,
                        )
                    )
        else:
            source_type = (
                TimelineSourceType.DERIVED
                if target.provenance == ProvenanceType.AI_DERIVED
                else TimelineSourceType.MANUAL
            )
            source = ManualEvidenceSource(
                type=source_type.value,
                message="No linked source evidence is available for this record.",
            )

        return EvidenceResponse(
            profile_id=profile_id,
            entity_id=entity_id,
            entity_type=entity_type,
            source_type=source_type,
            provenance=target.provenance,
            verification_status=target.verification_status,
            source=source,
            saved_value=saved_value,
            correction_history=corrections,
        )
