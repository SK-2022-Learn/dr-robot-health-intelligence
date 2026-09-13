"""Public, structured contracts for Ask Dr. Robot."""

from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator

from app.safety.schemas import SafetyResult
from app.schemas.common import SchemaModel


class AgentIntent(StrEnum):
    DAILY_LOG = "DAILY_LOG"
    RECORD_LOOKUP = "RECORD_LOOKUP"
    TIMELINE_QUERY = "TIMELINE_QUERY"
    EVIDENCE_QUERY = "EVIDENCE_QUERY"
    ANALYTICS_QUERY = "ANALYTICS_QUERY"
    FAMILY_QUERY = "FAMILY_QUERY"
    DOCTOR_VISIT = "DOCTOR_VISIT"
    GENERAL_HEALTH_INFORMATION = "GENERAL_HEALTH_INFORMATION"
    UNSUPPORTED_MEDICAL_ACTION = "UNSUPPORTED_MEDICAL_ACTION"
    UNKNOWN = "UNKNOWN"


class AskRequest(SchemaModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = Field(default=None, max_length=36)
    include_trace: bool = False

    @field_validator("message")
    @classmethod
    def clean_message(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Message cannot be blank.")
        return cleaned


class AgentSource(SchemaModel):
    source_type: str
    label: str
    evidence_path: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    document_id: str | None = None
    page_number: int | None = None


class AskResponse(SchemaModel):
    request_id: str
    intent: AgentIntent
    answer: str
    conversation_id: str | None = None
    pending_id: str | None = None
    clarification_required: bool = False
    sources: list[AgentSource] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    safety: SafetyResult | None = None
    warnings: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    structured_result: dict[str, Any] | None = None
    nodes_run: list[str] | None = None
