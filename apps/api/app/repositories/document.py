"""Source-document and page persistence operations."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.enums import VectorIndexStatus
from app.database.models import DocumentPage, SourceDocument
from app.ingestion.types import ParsedPage


class DocumentRepository:
    def create(self, db: Session, document: SourceDocument) -> SourceDocument:
        db.add(document)
        db.flush()
        return document

    def get(self, db: Session, document_id: str) -> SourceDocument | None:
        return db.get(SourceDocument, document_id)

    def find_duplicate(self, db: Session, profile_id: str, file_hash: str) -> SourceDocument | None:
        statement = select(SourceDocument).where(
            SourceDocument.profile_id == profile_id,
            SourceDocument.file_hash == file_hash,
        )
        return db.scalar(statement)

    def list_for_profile(self, db: Session, profile_id: str) -> list[SourceDocument]:
        statement = (
            select(SourceDocument)
            .where(SourceDocument.profile_id == profile_id)
            .order_by(SourceDocument.created_at.desc(), SourceDocument.id.desc())
        )
        return list(db.scalars(statement))

    def replace_pages(self, db: Session, document: SourceDocument, pages: list[ParsedPage]) -> None:
        document.pages.clear()
        document.pages.extend(
            DocumentPage(document_id=document.id, page_number=page.page_number, text=page.text)
            for page in pages
        )
        db.flush()

    def list_pages(self, db: Session, document_id: str) -> list[DocumentPage]:
        statement = (
            select(DocumentPage)
            .where(DocumentPage.document_id == document_id)
            .order_by(DocumentPage.page_number)
        )
        return list(db.scalars(statement))

    def get_page(self, db: Session, document_id: str, page_number: int) -> DocumentPage | None:
        return db.scalar(
            select(DocumentPage).where(
                DocumentPage.document_id == document_id,
                DocumentPage.page_number == page_number,
            )
        )

    def indexed_count_for_profile(self, db: Session, profile_id: str) -> int:
        return int(
            db.scalar(
                select(func.count(SourceDocument.id)).where(
                    SourceDocument.profile_id == profile_id,
                    SourceDocument.vector_index_status == VectorIndexStatus.INDEXED,
                )
            )
            or 0
        )
