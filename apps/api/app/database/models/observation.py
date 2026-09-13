"""Numeric or textual measurements attached to one profile."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Enum, Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.database.enums import ProvenanceType, VerificationStatus

if TYPE_CHECKING:
    from app.database.models.evidence_link import EvidenceLink
    from app.database.models.health_event import HealthEvent
    from app.database.models.health_profile import HealthProfile


class Observation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "observations"
    __table_args__ = (
        CheckConstraint(
            "value_number IS NOT NULL OR value_text IS NOT NULL",
            name="ck_observation_has_value",
        ),
        Index("ix_observations_profile_observed", "profile_id", "observed_at"),
    )

    profile_id: Mapped[str] = mapped_column(ForeignKey("health_profiles.id"))
    health_event_id: Mapped[str | None] = mapped_column(
        ForeignKey("health_events.id"), nullable=True
    )
    source_message_id: Mapped[str | None] = mapped_column(
        ForeignKey("messages.id"), nullable=True, index=True
    )
    code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    display_name: Mapped[str] = mapped_column(String(250))
    value_number: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reference_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    reference_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    interpretation: Mapped[str | None] = mapped_column(String(250), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    provenance: Mapped[ProvenanceType] = mapped_column(Enum(ProvenanceType, native_enum=False))
    verification_status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus, native_enum=False), default=VerificationStatus.PENDING
    )

    profile: Mapped[HealthProfile] = relationship(back_populates="observations")
    health_event: Mapped[HealthEvent | None] = relationship(back_populates="observations")
    evidence_links: Mapped[list[EvidenceLink]] = relationship(back_populates="observation")
