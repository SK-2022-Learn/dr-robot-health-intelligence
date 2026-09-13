"""Family relationship contracts."""

from datetime import datetime

from pydantic import model_validator

from app.database.enums import RelationshipType
from app.schemas.common import SchemaModel
from app.schemas.profile import ProfileRead


class FamilyRelationshipCreate(SchemaModel):
    source_profile_id: str
    target_profile_id: str
    relationship_type: RelationshipType

    @model_validator(mode="after")
    def profiles_must_differ(self) -> "FamilyRelationshipCreate":
        if self.source_profile_id == self.target_profile_id:
            raise ValueError("Source and target profiles must be different.")
        return self


class FamilyRelationshipRead(FamilyRelationshipCreate):
    id: str
    created_at: datetime


class FamilyRead(SchemaModel):
    profiles: list[ProfileRead]
    relationships: list[FamilyRelationshipRead]
