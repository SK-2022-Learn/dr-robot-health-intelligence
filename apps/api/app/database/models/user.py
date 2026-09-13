"""Prototype user identity without authentication credentials."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.database.models.health_profile import HealthProfile


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Owns health profiles; authentication may be added in a later phase."""

    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(320), unique=True, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    profiles: Mapped[list[HealthProfile]] = relationship(back_populates="owner")
