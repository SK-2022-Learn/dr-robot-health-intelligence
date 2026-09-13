"""Untrusted structured candidates awaiting explicit human review."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.database.enums import CandidateStatus

if TYPE_CHECKING:
    from app.database.models.source_document import SourceDocument
    from app.database.models.user import User


class ExtractedCandidate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "extracted_candidates"

    document_id: Mapped[str] = mapped_column(ForeignKey("source_documents.id"), index=True)
    candidate_type: Mapped[str] = mapped_column(String(100))
    raw_text: Mapped[str] = mapped_column(Text)
    structured_data: Mapped[dict[str, Any]] = mapped_column(JSON)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[CandidateStatus] = mapped_column(
        Enum(CandidateStatus, native_enum=False), default=CandidateStatus.PENDING
    )
    reviewed_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    document: Mapped[SourceDocument] = relationship(back_populates="candidates")
    reviewed_by: Mapped[User | None] = relationship(foreign_keys=[reviewed_by_user_id])
