"""Observation contracts requiring a numeric or textual value."""

from datetime import datetime

from pydantic import model_validator

from app.database.enums import ProvenanceType, VerificationStatus
from app.schemas.common import IdentityTimestamps, SchemaModel


class ObservationCreate(SchemaModel):
    profile_id: str
    health_event_id: str | None = None
    source_message_id: str | None = None
    code: str | None = None
    display_name: str
    value_number: float | None = None
    value_text: str | None = None
    unit: str | None = None
    reference_low: float | None = None
    reference_high: float | None = None
    interpretation: str | None = None
    observed_at: datetime
    provenance: ProvenanceType
    verification_status: VerificationStatus = VerificationStatus.PENDING

    @model_validator(mode="after")
    def require_value(self) -> "ObservationCreate":
        if self.value_number is None and self.value_text is None:
            raise ValueError("At least one observation value must be provided.")
        return self


class ObservationUpdate(SchemaModel):
    value_number: float | None = None
    value_text: str | None = None
    unit: str | None = None
    interpretation: str | None = None
    verification_status: VerificationStatus | None = None


class ObservationRead(IdentityTimestamps, ObservationCreate):
    pass
