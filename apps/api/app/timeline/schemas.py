"""Normalized contracts for trusted timeline, evidence, and structural gaps."""

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.database.enums import ProvenanceType, VerificationStatus


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TimelineEntityType(StrEnum):
    HEALTH_EVENT = "health_event"
    OBSERVATION = "observation"
    MEDICATION = "medication"
    SYMPTOM = "symptom"


class TimelineType(StrEnum):
    CONDITION = "CONDITION"
    LAB = "LAB"
    MEASUREMENT = "MEASUREMENT"
    MEDICATION = "MEDICATION"
    SYMPTOM = "SYMPTOM"
    PROCEDURE = "PROCEDURE"
    HOSPITALIZATION = "HOSPITALIZATION"
    LIFESTYLE = "LIFESTYLE"
    NOTE = "NOTE"


class TimelineSourceType(StrEnum):
    DOCUMENT = "DOCUMENT"
    CHAT = "CHAT"
    MANUAL = "MANUAL"
    DERIVED = "DERIVED"


class DatePrecision(StrEnum):
    EXACT = "EXACT"
    UNKNOWN = "UNKNOWN"


class TimelineItem(StrictModel):
    id: str
    entity_id: str
    entity_type: TimelineEntityType
    timeline_type: TimelineType
    title: str
    description: str | None
    occurred_at: datetime | None
    end_at: datetime | None
    date_precision: DatePrecision
    provenance: ProvenanceType
    verification_status: VerificationStatus
    confidence: float | None
    source_type: TimelineSourceType
    source_document_id: str | None
    source_message_id: str | None
    has_evidence: bool
    has_correction: bool
    created_at: datetime


class TimelineResponse(StrictModel):
    profile_id: str
    items: list[TimelineItem]
    total: int
    limit: int
    offset: int


class DocumentEvidenceSource(StrictModel):
    type: Literal["DOCUMENT"] = "DOCUMENT"
    document_id: str
    filename: str
    document_date: date | None
    page_number: int | None
    excerpt: str | None
    page_text: str | None
    view_source_path: str


class ChatEvidenceSource(StrictModel):
    type: Literal["CHAT"] = "CHAT"
    conversation_id: str
    message_id: str
    message: str
    message_timestamp: datetime
    label: Literal["USER-REPORTED SOURCE"] = "USER-REPORTED SOURCE"


class ManualEvidenceSource(StrictModel):
    type: Literal["MANUAL", "DERIVED"]
    message: str


EvidenceSource = Annotated[
    DocumentEvidenceSource | ChatEvidenceSource | ManualEvidenceSource,
    Field(discriminator="type"),
]


class CorrectionHistoryItem(StrictModel):
    action: str
    original_value: str | None
    corrected_value: str | None
    changed_fields: list[str]
    corrected_at: datetime
    actor: str | None


class EvidenceResponse(StrictModel):
    profile_id: str
    entity_id: str
    entity_type: TimelineEntityType
    source_type: TimelineSourceType
    provenance: ProvenanceType
    verification_status: VerificationStatus
    source: EvidenceSource
    saved_value: str | None
    correction_history: list[CorrectionHistoryItem]


class MissingEvidenceType(StrEnum):
    MISSING_SOURCE = "MISSING_SOURCE"
    MISSING_DATE = "MISSING_DATE"
    UNVERIFIED_FACT = "UNVERIFIED_FACT"
    STALE_MEDICATION_REVIEW = "STALE_MEDICATION_REVIEW"
    MISSING_EXPECTED_DOCUMENTATION = "MISSING_EXPECTED_DOCUMENTATION"


class MissingEvidenceGap(StrictModel):
    type: MissingEvidenceType
    entity_type: TimelineEntityType
    entity_id: str
    message: str


class MissingEvidenceResponse(StrictModel):
    profile_id: str
    gaps: list[MissingEvidenceGap]
