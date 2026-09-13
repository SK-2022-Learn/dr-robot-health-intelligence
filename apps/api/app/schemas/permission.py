"""Consent contracts requiring a user or profile grantee."""

from pydantic import model_validator

from app.database.enums import AccessLevel
from app.schemas.common import IdentityTimestamps, SchemaModel


class ConsentPermissionCreate(SchemaModel):
    profile_id: str
    grantee_user_id: str | None = None
    grantee_profile_id: str | None = None
    access_level: AccessLevel
    scope: str | None = None

    @model_validator(mode="after")
    def require_grantee(self) -> "ConsentPermissionCreate":
        if self.grantee_user_id is None and self.grantee_profile_id is None:
            raise ValueError("At least one consent grantee must be provided.")
        return self


class ConsentPermissionUpdate(SchemaModel):
    access_level: AccessLevel | None = None
    scope: str | None = None


class ConsentPermissionRead(IdentityTimestamps, ConsentPermissionCreate):
    pass
