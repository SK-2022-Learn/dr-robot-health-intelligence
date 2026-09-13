"""User contracts without authentication fields."""

from pydantic import Field

from app.schemas.common import IdentityTimestamps, SchemaModel


class UserCreate(SchemaModel):
    username: str
    email: str | None = Field(default=None, max_length=320)
    is_active: bool = True


class UserUpdate(SchemaModel):
    email: str | None = Field(default=None, max_length=320)
    is_active: bool | None = None


class UserRead(IdentityTimestamps):
    username: str
    email: str | None
    is_active: bool
