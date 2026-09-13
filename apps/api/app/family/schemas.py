"""Public, permission-safe contracts for family intelligence."""

from enum import StrEnum

from pydantic import Field

from app.database.enums import AccessLevel, RelationshipType, VerificationStatus
from app.schemas.common import SchemaModel
from app.schemas.family import FamilyRelationshipRead


class FamilyRecordState(StrEnum):
    DOCUMENTED = "DOCUMENTED"
    NOT_DOCUMENTED = "NOT_DOCUMENTED"
    UNKNOWN = "UNKNOWN"
    PRIVATE = "PRIVATE"


class FamilyDataConfidence(StrEnum):
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"


class FamilyProfileSummary(SchemaModel):
    profile_id: str
    label: str
    relationship_to_owner: RelationshipType
    access_level: AccessLevel
    is_private: bool
    permission_id: str | None = None
    documented_condition_count: int | None = None
    shared_conditions: list[str] | None = None


class FamilyGraphResponse(SchemaModel):
    requester_user_id: str
    selected_profile_id: str
    profiles: list[FamilyProfileSummary]
    relationships: list[FamilyRelationshipRead]


class FamilyEvidenceReference(SchemaModel):
    health_event_id: str
    evidence_path: str
    source_count: int = Field(ge=0)


class FamilyConditionContributor(SchemaModel):
    profile_id: str
    label: str
    access_level: AccessLevel
    state: FamilyRecordState
    generation: int
    branch: str
    health_event_id: str | None = None
    verification_status: VerificationStatus | None = None
    evidence: list[FamilyEvidenceReference] = Field(default_factory=list)


class FamilyConditionPattern(SchemaModel):
    condition_name: str
    profile_count: int = Field(ge=2)
    permitted_profile_count: int = Field(ge=1)
    generation_count: int = Field(ge=1)
    branches: list[str]
    contributing_profiles: list[FamilyConditionContributor]
    profile_states: list[FamilyConditionContributor]
    evidence_count: int = Field(ge=0)
    confidence: FamilyDataConfidence
    statement: str
    notes: list[str]


class FamilyPatternsResponse(SchemaModel):
    requester_user_id: str
    selected_profile_id: str
    patterns: list[FamilyConditionPattern]


class FamilyPermissionUpdate(SchemaModel):
    requester_user_id: str
    access_level: AccessLevel


class FamilyPermissionRead(SchemaModel):
    permission_id: str
    profile_id: str
    access_level: AccessLevel
    scope: str | None
