"""Traceable links from trusted facts back to source documents."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, UUIDPrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    from app.database.models.health_event import HealthEvent
    from app.database.models.medication import Medication
    from app.database.models.observation import Observation
    from app.database.models.source_document import SourceDocument
    from app.database.models.symptom import Symptom


class EvidenceLink(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "evidence_links"
    __table_args__ = (
        CheckConstraint(
            "health_event_id IS NOT NULL OR observation_id IS NOT NULL "
            "OR medication_id IS NOT NULL OR symptom_id IS NOT NULL",
            name="ck_evidence_has_target",
        ),
    )

    health_event_id: Mapped[str | None] = mapped_column(
        ForeignKey("health_events.id"), nullable=True
    )
    observation_id: Mapped[str | None] = mapped_column(ForeignKey("observations.id"), nullable=True)
    medication_id: Mapped[str | None] = mapped_column(ForeignKey("medications.id"), nullable=True)
    symptom_id: Mapped[str | None] = mapped_column(ForeignKey("symptoms.id"), nullable=True)
    source_document_id: Mapped[str] = mapped_column(ForeignKey("source_documents.id"), index=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    health_event: Mapped[HealthEvent | None] = relationship(back_populates="evidence_links")
    observation: Mapped[Observation | None] = relationship(back_populates="evidence_links")
    medication: Mapped[Medication | None] = relationship(back_populates="evidence_links")
    symptom: Mapped[Symptom | None] = relationship(back_populates="evidence_links")
    source_document: Mapped[SourceDocument] = relationship(back_populates="evidence_links")
