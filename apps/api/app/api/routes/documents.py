"""Document upload, metadata, and raw page-text endpoints."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.orm import Session

from app.database.models import DocumentPage, SourceDocument
from app.database.session import get_db
from app.schemas.document import DocumentDetail, DocumentPageRead, SourceDocumentSummary
from app.services.document import DocumentService, get_document_service

router = APIRouter(tags=["documents"])


@router.post(
    "/profiles/{profile_id}/documents",
    response_model=SourceDocumentSummary,
    status_code=status.HTTP_201_CREATED,
)
def upload_document(
    profile_id: str,
    db: Annotated[Session, Depends(get_db)],
    file: Annotated[UploadFile, File()],
    service: Annotated[DocumentService, Depends(get_document_service)],
    document_date: Annotated[date | None, Form()] = None,
) -> SourceDocument:
    return service.upload(
        db,
        profile_id,
        stream=file.file,
        filename=file.filename or "",
        mime_type=file.content_type or "application/octet-stream",
        document_date=document_date,
    )


@router.get("/documents/{document_id}", response_model=DocumentDetail)
def get_document(
    document_id: str,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> SourceDocument:
    return service.get_document(db, document_id)


@router.get("/documents/{document_id}/pages", response_model=list[DocumentPageRead])
def list_document_pages(
    document_id: str,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> list[DocumentPage]:
    return service.list_pages(db, document_id)
