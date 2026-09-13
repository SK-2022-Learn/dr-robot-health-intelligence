"""Strongly typed contracts for daily health extraction and review."""

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.database.enums import MessageRole, PendingHealthEntryStatus
from app.safety.schemas import SafetyResult


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class GlucoseContext(StrEnum):
    FASTING = "FASTING"
    BEFORE_MEAL = "BEFORE_MEAL"
    AFTER_MEAL = "AFTER_MEAL"
    RANDOM = "RANDOM"
    UNKNOWN = "UNKNOWN"


class SymptomSeverity(StrEnum):
    MILD = "MILD"
    MODERATE = "MODERATE"
    SEVERE = "SEVERE"
    UNKNOWN = "UNKNOWN"


class GlucoseEntry(StrictModel):
    entry_type: Literal["glucose"]
    value: float = Field(gt=0, le=2000)
    unit: Literal["mg/dL", "mmol/L"] = "mg/dL"
    context: GlucoseContext = GlucoseContext.UNKNOWN
    observed_at: datetime | None = None
    confidence: float = Field(ge=0, le=1)


class BloodPressureEntry(StrictModel):
    entry_type: Literal["blood_pressure"]
    systolic: int = Field(ge=30, le=350)
    diastolic: int = Field(ge=20, le=250)
    unit: Literal["mmHg"] = "mmHg"
    observed_at: datetime | None = None
    confidence: float = Field(ge=0, le=1)


class WeightEntry(StrictModel):
    entry_type: Literal["weight"]
    value: float = Field(gt=0, le=1500)
    unit: Literal["kg", "lb"] | None = None
    observed_at: datetime | None = None
    confidence: float = Field(ge=0, le=1)


ObservationEntry = Annotated[
    GlucoseEntry | BloodPressureEntry | WeightEntry,
    Field(discriminator="entry_type"),
]


class SleepEntry(StrictModel):
    duration_minutes: int = Field(gt=0, le=1440)
    sleep_date: date | None = None
    quality: str | None = Field(default=None, max_length=100)
    confidence: float = Field(ge=0, le=1)


class ActivityEntry(StrictModel):
    activity_type: str = Field(min_length=1, max_length=100)
    duration_minutes: int | None = Field(default=None, gt=0, le=1440)
    distance: float | None = Field(default=None, gt=0, le=10000)
    distance_unit: Literal["m", "km", "mi"] | None = None
    observed_at: datetime | None = None
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def require_measure(self) -> "ActivityEntry":
        if self.duration_minutes is None and self.distance is None:
            raise ValueError("Activity requires a duration or distance.")
        if self.distance is not None and self.distance_unit is None:
            raise ValueError("Activity distance requires a unit.")
        return self


class DailySymptomEntry(StrictModel):
    name: str = Field(min_length=1, max_length=250)
    severity: SymptomSeverity = SymptomSeverity.UNKNOWN
    started_at: datetime | None = None
    duration_text: str | None = Field(default=None, max_length=250)
    notes: str | None = Field(default=None, max_length=1000)
    confidence: float = Field(ge=0, le=1)


class ClarificationQuestion(StrictModel):
    field: str = Field(min_length=1, max_length=100)
    question: str = Field(min_length=1, max_length=300)
    options: list[str] = Field(min_length=2, max_length=8)


class DailyHealthExtraction(StrictModel):
    observations: list[ObservationEntry] = Field(default_factory=list, max_length=20)
    symptoms: list[DailySymptomEntry] = Field(default_factory=list, max_length=20)
    activities: list[ActivityEntry] = Field(default_factory=list, max_length=20)
    sleep_entries: list[SleepEntry] = Field(default_factory=list, max_length=20)
    clarifications: list[ClarificationQuestion] = Field(default_factory=list, max_length=20)
    warnings: list[str] = Field(default_factory=list, max_length=20)


class ConversationCreateRequest(StrictModel):
    title: str | None = Field(default="Daily health log", min_length=1, max_length=250)


class ChatMessageRequest(StrictModel):
    content: str = Field(min_length=1, max_length=2000)

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Message content cannot be blank.")
        return cleaned


class ClarificationRequest(StrictModel):
    answers: dict[str, str] = Field(min_length=1, max_length=20)


class PendingCorrectionRequest(StrictModel):
    extraction: DailyHealthExtraction


class MessageView(StrictModel):
    id: str
    conversation_id: str
    role: MessageRole
    content: str
    created_at: datetime


class TrustedRecordView(StrictModel):
    record_type: Literal["observations", "symptoms"]
    record_id: str


class PendingHealthEntryView(StrictModel):
    id: str
    conversation_id: str
    message_id: str
    profile_id: str
    extraction: DailyHealthExtraction
    status: PendingHealthEntryStatus
    was_corrected: bool
    trusted_records: list[TrustedRecordView]
    created_at: datetime
    updated_at: datetime


class ConversationSummary(StrictModel):
    id: str
    profile_id: str
    title: str | None
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationSummary):
    messages: list[MessageView]
    pending_entries: list[PendingHealthEntryView]


class ChatResponseStatus(StrEnum):
    STRUCTURED_PREVIEW = "STRUCTURED_PREVIEW"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    INFORMATIONAL = "INFORMATIONAL"
    SAFETY_BOUNDARY = "SAFETY_BOUNDARY"


class ChatMessageResponse(StrictModel):
    message_id: str
    pending_id: str | None
    status: ChatResponseStatus
    extraction: DailyHealthExtraction | None
    questions: list[ClarificationQuestion]
    assistant_message: str
    safety: SafetyResult | None = None


class ConfirmationResponse(StrictModel):
    pending: PendingHealthEntryView
    trusted_records: list[TrustedRecordView]
    already_confirmed: bool
