"""Strict model-output schemas for explicitly supported document facts."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ExtractionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceCandidate(ExtractionModel):
    confidence: float = Field(ge=0, le=1)
    evidence_text: str = Field(min_length=1, max_length=2000)
    page_number: int | None = Field(default=None, ge=1)


class ConditionCandidate(EvidenceCandidate):
    condition_name: str = Field(min_length=1, max_length=250)
    status: str | None = Field(default=None, max_length=100)
    onset_date: date | None = None
    resolved_date: date | None = None


class MedicationCandidate(EvidenceCandidate):
    name: str = Field(min_length=1, max_length=250)
    dose: str | None = Field(default=None, max_length=100)
    dose_unit: str | None = Field(default=None, max_length=50)
    frequency: str | None = Field(default=None, max_length=100)
    route: str | None = Field(default=None, max_length=100)
    start_date: date | None = None
    end_date: date | None = None
    active_status: Literal["active", "inactive", "unknown"] | None = None


class ValueCandidate(EvidenceCandidate):
    value_number: float | None = None
    value_text: str | None = Field(default=None, min_length=1, max_length=500)

    @model_validator(mode="after")
    def require_value(self) -> "ValueCandidate":
        if self.value_number is None and self.value_text is None:
            raise ValueError("At least one value must be provided.")
        return self


class LabCandidate(ValueCandidate):
    test_name: str = Field(min_length=1, max_length=250)
    unit: str | None = Field(default=None, max_length=50)
    reference_low: float | None = None
    reference_high: float | None = None
    reference_range_text: str | None = Field(default=None, max_length=250)
    collected_date: date | None = None
    interpretation: str | None = Field(default=None, max_length=250)


class SymptomCandidate(EvidenceCandidate):
    name: str = Field(min_length=1, max_length=250)
    severity: str | None = Field(default=None, max_length=100)
    started_at: datetime | None = None
    ended_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=1000)


class MeasurementCandidate(ValueCandidate):
    measurement_name: str = Field(min_length=1, max_length=250)
    unit: str | None = Field(default=None, max_length=50)
    context: str | None = Field(default=None, max_length=500)
    observed_at: datetime | None = None


class DocumentExtractionResult(ExtractionModel):
    conditions: list[ConditionCandidate] = Field(default_factory=list)
    medications: list[MedicationCandidate] = Field(default_factory=list)
    labs: list[LabCandidate] = Field(default_factory=list)
    symptoms: list[SymptomCandidate] = Field(default_factory=list)
    measurements: list[MeasurementCandidate] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    document_date: date | None = None
