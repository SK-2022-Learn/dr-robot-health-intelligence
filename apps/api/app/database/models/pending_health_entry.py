"""Server-persisted structured chat data awaiting explicit user review."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.database.enums import PendingHealthEntryStatus

if TYPE_CHECKING:
    from app.database.models.conversation import Conversation
    from app.database.models.health_profile import HealthProfile
    from app.database.models.message import Message


class PendingHealthEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pending_health_entries"
    __table_args__ = (
        Index("ix_pending_profile_status", "profile_id", "status"),
        Index("ix_pending_conversation_created", "conversation_id", "created_at"),
    )

    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"))
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id"), unique=True)
    profile_id: Mapped[str] = mapped_column(ForeignKey("health_profiles.id"))
    structured_data: Mapped[dict[str, Any]] = mapped_column(JSON)
    original_structured_data: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[PendingHealthEntryStatus] = mapped_column(
        Enum(PendingHealthEntryStatus, native_enum=False)
    )
    was_corrected: Mapped[bool] = mapped_column(Boolean, default=False)
    trusted_records: Mapped[list[dict[str, str]] | None] = mapped_column(JSON, nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    conversation: Mapped[Conversation] = relationship(back_populates="pending_entries")
    message: Mapped[Message] = relationship(back_populates="pending_entry")
    profile: Mapped[HealthProfile] = relationship(back_populates="pending_health_entries")
