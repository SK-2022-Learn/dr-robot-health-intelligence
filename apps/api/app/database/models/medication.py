"""Medication records without interaction or prescribing logic."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.database.enums import ProvenanceType, VerificationStatus

if TYPE_CHECKING:
    from app.database.models.evidence_link import EvidenceLink
    from app.database.models.health_event import HealthEvent
    from app.database.models.health_profile import HealthProfile


class Medication(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "medications"

    profile_id: Mapped[str] = mapped_column(ForeignKey("health_profiles.id"), index=True)
    name: Mapped[str] = mapped_column(String(250))
    dose: Mapped[str | None] = mapped_column(String(100), nullable=True)
    dose_unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    frequency: Mapped[str | None] = mapped_column(String(100), nullable=True)
    route: Mapped[str | None] = mapped_column(String(100), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    provenance: Mapped[ProvenanceType] = mapped_column(Enum(ProvenanceType, native_enum=False))
    verification_status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus, native_enum=False), default=VerificationStatus.PENDING
    )
    source_event_id: Mapped[str | None] = mapped_column(
        ForeignKey("health_events.id"), nullable=True
    )

    profile: Mapped[HealthProfile] = relationship(back_populates="medications")
    source_event: Mapped[HealthEvent | None] = relationship(back_populates="medications")
    evidence_links: Mapped[list[EvidenceLink]] = relationship(back_populates="medication")
