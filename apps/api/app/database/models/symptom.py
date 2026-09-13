"""Symptoms reported for one health profile."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.database.enums import ProvenanceType, VerificationStatus

if TYPE_CHECKING:
    from app.database.models.evidence_link import EvidenceLink
    from app.database.models.health_event import HealthEvent
    from app.database.models.health_profile import HealthProfile


class Symptom(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "symptoms"

    profile_id: Mapped[str] = mapped_column(ForeignKey("health_profiles.id"), index=True)
    name: Mapped[str] = mapped_column(String(250))
    severity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    provenance: Mapped[ProvenanceType] = mapped_column(Enum(ProvenanceType, native_enum=False))
    verification_status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus, native_enum=False), default=VerificationStatus.PENDING
    )
    source_event_id: Mapped[str | None] = mapped_column(
        ForeignKey("health_events.id"), nullable=True
    )
    source_message_id: Mapped[str | None] = mapped_column(
        ForeignKey("messages.id"), nullable=True, index=True
    )

    profile: Mapped[HealthProfile] = relationship(back_populates="symptoms")
    source_event: Mapped[HealthEvent | None] = relationship(back_populates="symptoms")
    evidence_links: Mapped[list[EvidenceLink]] = relationship(back_populates="symptom")
