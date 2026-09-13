"""Structured Doctor Visit brief contracts."""

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from app.analytics.schemas import TrendAnalysisResult
from app.database.enums import ProvenanceType, VerificationStatus
from app.timeline.schemas import TimelineEntityType, TimelineSourceType, TimelineType


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RewriteStatus(StrEnum):
    NOT_REQUESTED = "NOT_REQUESTED"
    LLM_ACCEPTED = "LLM_ACCEPTED"
    UNAVAILABLE = "UNAVAILABLE"
    REJECTED_FACT_CHANGE = "REJECTED_FACT_CHANGE"
    REJECTED_SAFETY = "REJECTED_SAFETY"
    INVALID_RESPONSE = "INVALID_RESPONSE"


class VisitEvidenceReference(StrictModel):
    entity_type: TimelineEntityType
    entity_id: str
    source_type: TimelineSourceType
    source_label: str
    provenance: ProvenanceType
    verification_status: VerificationStatus
    has_evidence: bool
    evidence_path: str


class KnownHistoryItem(StrictModel):
    record_id: str
    title: str
    timeline_type: TimelineType
    documented_date: datetime | None
    end_date: datetime | None
    evidence: VisitEvidenceReference


class MedicationSummaryItem(StrictModel):
    record_id: str
    name: str
    dose: str | None
    dose_unit: str | None
    frequency: str | None
    route: str | None
    start_date: date | None
    end_date: date | None
    last_updated_at: datetime
    reconciliation_needed: bool
    evidence: VisitEvidenceReference


class ObservationSummaryItem(StrictModel):
    record_id: str
    name: str
    value: str
    unit: str | None
    observed_at: datetime
    interpretation: str | None
    evidence: VisitEvidenceReference


class SymptomSummaryItem(StrictModel):
    name: str
    report_count: int
    most_recent: datetime
    statement: str
    evidence: list[VisitEvidenceReference]


class RecentChangeItem(StrictModel):
    key: str
    statement: str
    analysis: TrendAnalysisResult


class VisitMissingEvidenceItem(StrictModel):
    type: str
    message: str
    entity_type: TimelineEntityType | None = None
    entity_id: str | None = None


class DiscussionQuestion(StrictModel):
    question_id: str
    trigger: str
    question: str


class EvidenceSummaryItem(StrictModel):
    key: str
    label: str
    count: int


class DoctorVisitBrief(StrictModel):
    profile_id: str
    profile_display_name: str
    profile_age: int | None
    date_of_birth: date | None
    relationship_to_owner: str
    generated_at: datetime
    data_cutoff: datetime
    summary_version: str
    overview: str
    overview_source: str
    rewrite_status: RewriteStatus
    known_history: list[KnownHistoryItem]
    recent_changes: list[RecentChangeItem]
    medications: list[MedicationSummaryItem]
    recent_labs: list[ObservationSummaryItem]
    recent_measurements: list[ObservationSummaryItem]
    recent_symptoms: list[SymptomSummaryItem]
    missing_evidence: list[VisitMissingEvidenceItem]
    questions_to_discuss: list[DiscussionQuestion]
    evidence_summary: list[EvidenceSummaryItem]
    safety_notes: list[str]
