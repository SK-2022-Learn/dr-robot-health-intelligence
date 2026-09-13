"""Symptom contracts without trend or diagnostic behavior."""

from datetime import datetime

from pydantic import Field

from app.database.enums import ProvenanceType, VerificationStatus
from app.schemas.common import IdentityTimestamps, SchemaModel


class SymptomCreate(SchemaModel):
    profile_id: str
    name: str
    severity: int | None = Field(default=None, ge=0, le=10)
    started_at: datetime | None = None
    ended_at: datetime | None = None
    notes: str | None = None
    provenance: ProvenanceType
    verification_status: VerificationStatus = VerificationStatus.PENDING
    source_event_id: str | None = None
    source_message_id: str | None = None


class SymptomUpdate(SchemaModel):
    severity: int | None = Field(default=None, ge=0, le=10)
    ended_at: datetime | None = None
    notes: str | None = None
    verification_status: VerificationStatus | None = None


class SymptomRead(IdentityTimestamps, SymptomCreate):
    pass
