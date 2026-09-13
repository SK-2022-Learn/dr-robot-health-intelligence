"""Safe source-document ingestion and read contracts."""

from datetime import date, datetime

from app.database.enums import DocumentStatus, VectorIndexStatus
from app.schemas.common import IdentityTimestamps, SchemaModel


class SourceDocumentCreate(SchemaModel):
    profile_id: str
    original_filename: str
    stored_filename: str
    mime_type: str
    file_hash: str | None = None
    storage_path: str
    document_date: date | None = None
    status: DocumentStatus = DocumentStatus.UPLOADED
    extracted_text: str | None = None
    page_count: int = 0


class SourceDocumentUpdate(SchemaModel):
    document_date: date | None = None
    status: DocumentStatus | None = None
    extracted_text: str | None = None
    page_count: int | None = None


class SourceDocumentRead(IdentityTimestamps, SourceDocumentCreate):
    pass


class SourceDocumentSummary(IdentityTimestamps):
    """Safe UI metadata that excludes storage paths and extracted content."""

    profile_id: str
    original_filename: str
    mime_type: str
    document_date: date | None
    status: DocumentStatus
    page_count: int
    has_extracted_text: bool
    vector_index_status: VectorIndexStatus
    vector_indexed_at: datetime | None
    vector_chunk_count: int


class DocumentDetail(SourceDocumentSummary):
    pass


class DocumentPageRead(SchemaModel):
    id: str
    document_id: str
    page_number: int
    text: str
    created_at: datetime
