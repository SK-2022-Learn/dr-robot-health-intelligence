"""Normalized safety evaluation input and output contracts."""

from typing import Any

from pydantic import Field, field_validator

from app.safety.enums import SafetyCategory, SafetyDecision
from app.schemas.common import SchemaModel


class SafetyInput(SchemaModel):
    user_text: str = Field(min_length=1, max_length=4000)
    intent: str | None = Field(default=None, max_length=100)
    draft_response: str | None = Field(default=None, max_length=8000)
    profile_id: str | None = Field(default=None, max_length=36)
    context_type: str = Field(default="GENERAL_ASK", min_length=1, max_length=100)
    source: str = Field(default="API", min_length=1, max_length=100)

    @field_validator("user_text")
    @classmethod
    def clean_user_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Safety input cannot be blank.")
        return cleaned


class SafetyResult(SchemaModel):
    decision: SafetyDecision
    category: SafetyCategory
    rule_id: str
    message: str
    safe_response_override: str | None = None
    requires_professional_evaluation: bool = False
    emergency_guidance: bool = False
    audit_metadata: dict[str, Any] = Field(default_factory=dict)
    policy_version: str
