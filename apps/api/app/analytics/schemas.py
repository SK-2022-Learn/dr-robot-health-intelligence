"""Public contracts for reproducible personal-baseline analytics."""

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.database.enums import ProvenanceType, VerificationStatus
from app.timeline.schemas import TimelineSourceType


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AnalyticsMetric(StrEnum):
    GLUCOSE = "glucose"
    HBA1C = "hba1c"
    WEIGHT = "weight"
    SYSTOLIC_BLOOD_PRESSURE = "systolic_blood_pressure"
    DIASTOLIC_BLOOD_PRESSURE = "diastolic_blood_pressure"
    SLEEP_DURATION = "sleep_duration"
    ACTIVITY_DURATION = "activity_duration"


class GlucoseContext(StrEnum):
    FASTING = "FASTING"
    BEFORE_MEAL = "BEFORE_MEAL"
    AFTER_MEAL = "AFTER_MEAL"
    RANDOM = "RANDOM"


class TrendClassification(StrEnum):
    INCREASED = "INCREASED"
    DECREASED = "DECREASED"
    STABLE = "STABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class DataConfidence(StrEnum):
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"
    INSUFFICIENT = "INSUFFICIENT"


class ExplanationSource(StrEnum):
    LLM = "LLM"
    TEMPLATE = "TEMPLATE"


class AnalysisPeriod(StrictModel):
    start: date
    end: date
    days: int
    boundaries: str = "inclusive"


class NumericSummary(StrictModel):
    count: int
    mean: float | None
    median: float | None
    minimum: float | None
    maximum: float | None
    standard_deviation: float | None
    first_value: float | None
    last_value: float | None


class AnalyticsEvidence(StrictModel):
    observation_id: str
    recorded_at: datetime
    original_value: str
    normalized_value: float
    normalized_unit: str
    provenance: ProvenanceType
    verification_status: VerificationStatus
    source_type: TimelineSourceType
    source_label: str
    source_excerpt: str | None
    view_source_path: str | None
    evidence_path: str


class TrendAnalysisResult(StrictModel):
    profile_id: str
    metric: AnalyticsMetric
    metric_label: str
    context: GlucoseContext | None
    unit: str
    reference_date: date
    recent_period: AnalysisPeriod
    baseline_period: AnalysisPeriod
    recent_count: int
    baseline_count: int
    recent_summary: NumericSummary
    baseline_summary: NumericSummary
    absolute_change: float | None
    percent_change: float | None
    classification: TrendClassification
    confidence: DataConfidence
    confidence_reason: str
    missing_data: list[str]
    evidence_ids: list[str]
    evidence: list[AnalyticsEvidence]
    calculation_version: str
    stability_threshold_percent: float
    explanation: str
    explanation_source: ExplanationSource
    display_priority: int | None = None


class SymptomEvidence(StrictModel):
    symptom_id: str
    recorded_at: datetime
    severity: int | None
    provenance: ProvenanceType
    verification_status: VerificationStatus
    evidence_path: str


class SymptomFrequencyResult(StrictModel):
    profile_id: str
    symptom_name: str
    reference_date: date
    recent_period: AnalysisPeriod
    baseline_period: AnalysisPeriod
    recent_count: int
    baseline_count: int
    recent_rate_per_day: float | None
    baseline_rate_per_day: float | None
    percent_change: float | None
    classification: TrendClassification
    confidence: DataConfidence
    confidence_reason: str
    missing_data: list[str]
    evidence_ids: list[str]
    evidence: list[SymptomEvidence]
    calculation_version: str
    explanation: str


class AvailableMetric(StrictModel):
    metric: AnalyticsMetric
    label: str
    contexts: list[GlucoseContext]


class AvailableMetricsResponse(StrictModel):
    profile_id: str
    metrics: list[AvailableMetric]
    symptoms: list[str]


class WhatChangedRequest(StrictModel):
    since: date | None = None
    reference_date: date | None = None
    recent_days: int | None = Field(default=None, ge=1, le=365)
    baseline_days: int | None = Field(default=None, ge=1, le=730)
    include_explanation: bool = False

    @model_validator(mode="after")
    def validate_windows(self) -> "WhatChangedRequest":
        if self.since is not None and self.recent_days is not None:
            raise ValueError("Use either since or recent_days, not both.")
        if self.since and self.reference_date and self.since > self.reference_date:
            raise ValueError("since cannot be after reference_date.")
        return self


class WhatChangedResponse(StrictModel):
    profile_id: str
    results: list[TrendAnalysisResult]
