"""Medication record contracts without interaction logic."""

from datetime import date

from app.database.enums import ProvenanceType, VerificationStatus
from app.schemas.common import IdentityTimestamps, SchemaModel


class MedicationCreate(SchemaModel):
    profile_id: str
    name: str
    dose: str | None = None
    dose_unit: str | None = None
    frequency: str | None = None
    route: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_active: bool = True
    provenance: ProvenanceType
    verification_status: VerificationStatus = VerificationStatus.PENDING
    source_event_id: str | None = None


class MedicationUpdate(SchemaModel):
    dose: str | None = None
    dose_unit: str | None = None
    frequency: str | None = None
    route: str | None = None
    end_date: date | None = None
    is_active: bool | None = None
    verification_status: VerificationStatus | None = None


class MedicationRead(IdentityTimestamps, MedicationCreate):
    pass
