"""Longitudinal health-event contracts."""

from datetime import date

from pydantic import Field

from app.database.enums import HealthEventType, ProvenanceType, VerificationStatus
from app.schemas.common import IdentityTimestamps, SchemaModel


class HealthEventCreate(SchemaModel):
    event_type: HealthEventType
    event_date: date
    end_date: date | None = None
    title: str = Field(min_length=1, max_length=250)
    description: str | None = None
    verification_status: VerificationStatus = VerificationStatus.PENDING
    provenance: ProvenanceType
    confidence: float | None = Field(default=None, ge=0, le=1)
    source_document_id: str | None = None
    created_by_user_id: str | None = None


class HealthEventUpdate(SchemaModel):
    event_type: HealthEventType | None = None
    event_date: date | None = None
    end_date: date | None = None
    title: str | None = Field(default=None, min_length=1, max_length=250)
    description: str | None = None
    verification_status: VerificationStatus | None = None
    provenance: ProvenanceType | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    source_document_id: str | None = None


class HealthEventRead(IdentityTimestamps, HealthEventCreate):
    profile_id: str
