"""Shared SQLAlchemy declarative base and portable identity/timestamp mixins."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp for persisted lifecycle fields."""

    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Declarative metadata root imported by Alembic and tests."""


class UUIDPrimaryKeyMixin:
    """Use portable UUID strings rather than database-specific UUID columns."""

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))


class TimestampMixin:
    """Standard UTC creation and modification timestamps."""

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
