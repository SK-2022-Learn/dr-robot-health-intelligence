"""Conversation container without language-model integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.database.models.health_profile import HealthProfile
    from app.database.models.message import Message
    from app.database.models.pending_health_entry import PendingHealthEntry


class Conversation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "conversations"

    profile_id: Mapped[str] = mapped_column(ForeignKey("health_profiles.id"), index=True)
    title: Mapped[str | None] = mapped_column(String(250), nullable=True)

    profile: Mapped[HealthProfile] = relationship(back_populates="conversations")
    messages: Mapped[list[Message]] = relationship(back_populates="conversation")
    pending_entries: Mapped[list[PendingHealthEntry]] = relationship(back_populates="conversation")
