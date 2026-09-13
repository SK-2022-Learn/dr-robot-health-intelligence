"""Normalized, profile-scoped timeline aggregation over trusted tables."""

from datetime import UTC, date, datetime, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.database.enums import HealthEventType, ProvenanceType, VerificationStatus
from app.database.models import (
    AuditLog,
    EvidenceLink,
    ExtractedCandidate,
    HealthEvent,
    HealthProfile,
    Medication,
    Observation,
    SourceDocument,
    Symptom,
)
from app.timeline.evidence import format_target_value
from app.timeline.ordering import order_timeline_items
from app.timeline.schemas import (
    DatePrecision,
    TimelineEntityType,
    TimelineItem,
    TimelineResponse,
    TimelineSourceType,
    TimelineType,
)


def _as_datetime(value: date | datetime | None) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, time.min, tzinfo=UTC)
    return None


def _event_timeline_type(event_type: HealthEventType) -> TimelineType:
    supported = {
        HealthEventType.CONDITION: TimelineType.CONDITION,
        HealthEventType.LAB: TimelineType.LAB,
        HealthEventType.MEASUREMENT: TimelineType.MEASUREMENT,
        HealthEventType.MEDICATION: TimelineType.MEDICATION,
        HealthEventType.SYMPTOM: TimelineType.SYMPTOM,
        HealthEventType.PROCEDURE: TimelineType.PROCEDURE,
        HealthEventType.HOSPITALIZATION: TimelineType.HOSPITALIZATION,
        HealthEventType.LIFESTYLE: TimelineType.LIFESTYLE,
        HealthEventType.NOTE: TimelineType.NOTE,
    }
    return supported.get(event_type, TimelineType.NOTE)


class TimelineService:
    @staticmethod
    def _require_profile(db: Session, profile_id: str) -> None:
        if db.get(HealthProfile, profile_id) is None:
            raise ApiError(
                status_code=404,
                code="PROFILE_NOT_FOUND",
                message="Health profile was not found.",
            )

    @staticmethod
    def _evidence_maps(
        db: Session, profile_id: str
    ) -> tuple[dict[tuple[str, str], EvidenceLink], dict[str, str]]:
        links = db.scalars(
            select(EvidenceLink).join(SourceDocument).where(SourceDocument.profile_id == profile_id)
        ).all()
        by_target: dict[tuple[str, str], EvidenceLink] = {}
        document_by_target: dict[str, str] = {}
        for link in links:
            targets = (
                (TimelineEntityType.HEALTH_EVENT.value, link.health_event_id),
                (TimelineEntityType.OBSERVATION.value, link.observation_id),
                (TimelineEntityType.MEDICATION.value, link.medication_id),
                (TimelineEntityType.SYMPTOM.value, link.symptom_id),
            )
            for entity_type, entity_id in targets:
                if entity_id:
                    by_target[(entity_type, entity_id)] = link
                    document_by_target[entity_id] = link.source_document_id
        return by_target, document_by_target

    @staticmethod
    def _candidate_types(db: Session, profile_id: str) -> dict[tuple[str, str], str]:
        result: dict[tuple[str, str], str] = {}
        audits = db.scalars(
            select(AuditLog).where(
                AuditLog.action.in_(("CANDIDATE_ACCEPTED", "CANDIDATE_CORRECTED"))
            )
        ).all()
        for audit in audits:
            reference = (audit.after_state or {}).get("trusted_record", {})
            record_type = reference.get("record_type")
            record_id = reference.get("record_id")
            if not record_type or not record_id:
                continue
            candidate = db.get(ExtractedCandidate, audit.entity_id)
            if candidate and candidate.document.profile_id == profile_id:
                result[(record_type, record_id)] = candidate.candidate_type
        return result

    @staticmethod
    def _source(
        provenance: ProvenanceType,
        *,
        document_id: str | None,
        message_id: str | None,
    ) -> TimelineSourceType:
        if document_id:
            return TimelineSourceType.DOCUMENT
        if message_id:
            return TimelineSourceType.CHAT
        if provenance == ProvenanceType.AI_DERIVED:
            return TimelineSourceType.DERIVED
        if provenance in {ProvenanceType.AI_EXTRACTED, ProvenanceType.DOCUMENT_VERIFIED}:
            return TimelineSourceType.DOCUMENT
        return TimelineSourceType.MANUAL

    def list(
        self,
        db: Session,
        profile_id: str,
        *,
        sort: str = "desc",
        timeline_type: TimelineType | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> TimelineResponse:
        self._require_profile(db, profile_id)
        links, document_by_target = self._evidence_maps(db, profile_id)
        candidate_types = self._candidate_types(db, profile_id)
        items: list[TimelineItem] = []

        events = db.scalars(
            select(HealthEvent).where(
                HealthEvent.profile_id == profile_id,
                HealthEvent.verification_status != VerificationStatus.REJECTED,
            )
        ).all()
        for event in events:
            document_id = event.source_document_id or document_by_target.get(event.id)
            occurred_at = _as_datetime(event.event_date)
            items.append(
                TimelineItem(
                    id=f"health_event:{event.id}",
                    entity_id=event.id,
                    entity_type=TimelineEntityType.HEALTH_EVENT,
                    timeline_type=_event_timeline_type(event.event_type),
                    title=event.title,
                    description=event.description,
                    occurred_at=occurred_at,
                    end_at=_as_datetime(event.end_date),
                    date_precision=DatePrecision.EXACT,
                    provenance=event.provenance,
                    verification_status=event.verification_status,
                    confidence=event.confidence,
                    source_type=self._source(
                        event.provenance, document_id=document_id, message_id=None
                    ),
                    source_document_id=document_id,
                    source_message_id=None,
                    has_evidence=(
                        (TimelineEntityType.HEALTH_EVENT.value, event.id) in links
                        or document_id is not None
                    ),
                    has_correction=event.provenance == ProvenanceType.USER_CORRECTED,
                    created_at=event.created_at,
                )
            )

        observations = db.scalars(
            select(Observation).where(
                Observation.profile_id == profile_id,
                Observation.verification_status != VerificationStatus.REJECTED,
            )
        ).all()
        for observation in observations:
            document_id = document_by_target.get(observation.id)
            candidate_type = candidate_types.get(("observations", observation.id))
            kind = TimelineType.LAB if candidate_type == "lab" else TimelineType.MEASUREMENT
            items.append(
                TimelineItem(
                    id=f"observation:{observation.id}",
                    entity_id=observation.id,
                    entity_type=TimelineEntityType.OBSERVATION,
                    timeline_type=kind,
                    title=observation.display_name,
                    description=format_target_value(observation),
                    occurred_at=observation.observed_at,
                    end_at=None,
                    date_precision=DatePrecision.EXACT,
                    provenance=observation.provenance,
                    verification_status=observation.verification_status,
                    confidence=None,
                    source_type=self._source(
                        observation.provenance,
                        document_id=document_id,
                        message_id=observation.source_message_id,
                    ),
                    source_document_id=document_id,
                    source_message_id=observation.source_message_id,
                    has_evidence=(
                        (TimelineEntityType.OBSERVATION.value, observation.id) in links
                        or observation.source_message_id is not None
                    ),
                    has_correction=observation.provenance == ProvenanceType.USER_CORRECTED,
                    created_at=observation.created_at,
                )
            )

        medications = db.scalars(
            select(Medication).where(
                Medication.profile_id == profile_id,
                Medication.verification_status != VerificationStatus.REJECTED,
            )
        ).all()
        for medication in medications:
            document_id = document_by_target.get(medication.id)
            occurred_at = _as_datetime(medication.start_date)
            items.append(
                TimelineItem(
                    id=f"medication:{medication.id}",
                    entity_id=medication.id,
                    entity_type=TimelineEntityType.MEDICATION,
                    timeline_type=TimelineType.MEDICATION,
                    title=medication.name,
                    description=format_target_value(medication),
                    occurred_at=occurred_at,
                    end_at=_as_datetime(medication.end_date),
                    date_precision=(DatePrecision.EXACT if occurred_at else DatePrecision.UNKNOWN),
                    provenance=medication.provenance,
                    verification_status=medication.verification_status,
                    confidence=None,
                    source_type=self._source(
                        medication.provenance, document_id=document_id, message_id=None
                    ),
                    source_document_id=document_id,
                    source_message_id=None,
                    has_evidence=(TimelineEntityType.MEDICATION.value, medication.id) in links,
                    has_correction=medication.provenance == ProvenanceType.USER_CORRECTED,
                    created_at=medication.created_at,
                )
            )

        symptoms = db.scalars(
            select(Symptom).where(
                Symptom.profile_id == profile_id,
                Symptom.verification_status != VerificationStatus.REJECTED,
            )
        ).all()
        for symptom in symptoms:
            document_id = document_by_target.get(symptom.id)
            items.append(
                TimelineItem(
                    id=f"symptom:{symptom.id}",
                    entity_id=symptom.id,
                    entity_type=TimelineEntityType.SYMPTOM,
                    timeline_type=TimelineType.SYMPTOM,
                    title=symptom.name,
                    description=format_target_value(symptom),
                    occurred_at=symptom.started_at,
                    end_at=symptom.ended_at,
                    date_precision=(
                        DatePrecision.EXACT if symptom.started_at else DatePrecision.UNKNOWN
                    ),
                    provenance=symptom.provenance,
                    verification_status=symptom.verification_status,
                    confidence=None,
                    source_type=self._source(
                        symptom.provenance,
                        document_id=document_id,
                        message_id=symptom.source_message_id,
                    ),
                    source_document_id=document_id,
                    source_message_id=symptom.source_message_id,
                    has_evidence=(
                        (TimelineEntityType.SYMPTOM.value, symptom.id) in links
                        or symptom.source_message_id is not None
                    ),
                    has_correction=symptom.provenance == ProvenanceType.USER_CORRECTED,
                    created_at=symptom.created_at,
                )
            )

        if timeline_type:
            items = [item for item in items if item.timeline_type == timeline_type]
        if from_date:
            items = [
                item for item in items if item.occurred_at and item.occurred_at.date() >= from_date
            ]
        if to_date:
            items = [
                item for item in items if item.occurred_at and item.occurred_at.date() <= to_date
            ]
        ordered = order_timeline_items(items, sort)
        return TimelineResponse(
            profile_id=profile_id,
            items=ordered[offset : offset + limit],
            total=len(ordered),
            limit=limit,
            offset=offset,
        )
