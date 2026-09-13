"""Trusted longitudinal health events."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, Enum, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.database.enums import HealthEventType, ProvenanceType, VerificationStatus

if TYPE_CHECKING:
    from app.database.models.evidence_link import EvidenceLink
    from app.database.models.health_profile import HealthProfile
    from app.database.models.medication import Medication
    from app.database.models.observation import Observation
    from app.database.models.source_document import SourceDocument
    from app.database.models.symptom import Symptom
    from app.database.models.user import User


class HealthEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "health_events"
    __table_args__ = (Index("ix_health_events_profile_date", "profile_id", "event_date"),)

    profile_id: Mapped[str] = mapped_column(ForeignKey("health_profiles.id"))
    event_type: Mapped[HealthEventType] = mapped_column(Enum(HealthEventType, native_enum=False))
    event_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    title: Mapped[str] = mapped_column(String(250))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus, native_enum=False), default=VerificationStatus.PENDING
    )
    provenance: Mapped[ProvenanceType] = mapped_column(Enum(ProvenanceType, native_enum=False))
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_document_id: Mapped[str | None] = mapped_column(
        ForeignKey("source_documents.id"), nullable=True
    )
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    profile: Mapped[HealthProfile] = relationship(back_populates="health_events")
    source_document: Mapped[SourceDocument | None] = relationship(back_populates="health_events")
    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_user_id])
    observations: Mapped[list[Observation]] = relationship(back_populates="health_event")
    medications: Mapped[list[Medication]] = relationship(back_populates="source_event")
    symptoms: Mapped[list[Symptom]] = relationship(back_populates="source_event")
    evidence_links: Mapped[list[EvidenceLink]] = relationship(back_populates="health_event")
