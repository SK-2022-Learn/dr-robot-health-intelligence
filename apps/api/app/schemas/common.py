"""Shared Pydantic configuration and response fields."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SchemaModel(BaseModel):
    """Allow API schemas to validate directly from SQLAlchemy attributes."""

    model_config = ConfigDict(from_attributes=True)


class IdentityTimestamps(SchemaModel):
    id: str
    created_at: datetime
    updated_at: datetime
