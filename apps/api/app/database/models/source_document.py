"""Storage metadata for future document ingestion."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.database.enums import DocumentStatus, VectorIndexStatus

if TYPE_CHECKING:
    from app.database.models.document_page import DocumentPage
    from app.database.models.evidence_link import EvidenceLink
    from app.database.models.extracted_candidate import ExtractedCandidate
    from app.database.models.health_event import HealthEvent
    from app.database.models.health_profile import HealthProfile


class SourceDocument(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "source_documents"
    __table_args__ = (UniqueConstraint("profile_id", "file_hash", name="uq_document_profile_hash"),)

    profile_id: Mapped[str] = mapped_column(ForeignKey("health_profiles.id"), index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(255), unique=True)
    mime_type: Mapped[str] = mapped_column(String(150))
    file_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    storage_path: Mapped[str] = mapped_column(String(500))
    document_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, native_enum=False), default=DocumentStatus.UPLOADED
    )
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    vector_index_status: Mapped[VectorIndexStatus] = mapped_column(
        Enum(VectorIndexStatus, native_enum=False),
        default=VectorIndexStatus.NOT_INDEXED,
    )
    vector_indexed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    vector_chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    vector_index_error: Mapped[str | None] = mapped_column(String(100), nullable=True)

    profile: Mapped[HealthProfile] = relationship(back_populates="source_documents")
    health_events: Mapped[list[HealthEvent]] = relationship(back_populates="source_document")
    candidates: Mapped[list[ExtractedCandidate]] = relationship(back_populates="document")
    evidence_links: Mapped[list[EvidenceLink]] = relationship(back_populates="source_document")
    pages: Mapped[list[DocumentPage]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="DocumentPage.page_number"
    )

    @property
    def has_extracted_text(self) -> bool:
        return bool(self.extracted_text and self.extracted_text.strip())
