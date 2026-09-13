"""Health-profile request and response contracts."""

from datetime import date

from pydantic import Field

from app.database.enums import AccessLevel, RelationshipType
from app.schemas.common import IdentityTimestamps, SchemaModel


class ProfileCreate(SchemaModel):
    owner_user_id: str
    display_name: str = Field(min_length=1, max_length=150)
    relationship_to_owner: RelationshipType = RelationshipType.SELF
    date_of_birth: date | None = None
    sex: str | None = Field(default=None, max_length=50)
    access_level: AccessLevel = AccessLevel.PRIVATE
    is_active: bool = True


class ProfileUpdate(SchemaModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=150)
    relationship_to_owner: RelationshipType | None = None
    date_of_birth: date | None = None
    sex: str | None = Field(default=None, max_length=50)
    access_level: AccessLevel | None = None
    is_active: bool | None = None


class ProfileRead(IdentityTimestamps):
    owner_user_id: str
    display_name: str
    relationship_to_owner: RelationshipType
    date_of_birth: date | None
    sex: str | None
    access_level: AccessLevel
    is_active: bool
