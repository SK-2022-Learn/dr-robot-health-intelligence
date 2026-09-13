"""Secure document storage, raw parsing, persistence, and audit coordination."""

import logging
from datetime import date
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.errors import ApiError
from app.database.enums import DocumentStatus
from app.database.models import DocumentPage, SourceDocument
from app.database.session import REPOSITORY_ROOT
from app.ingestion.parser import DocumentParser
from app.ingestion.storage import LocalDocumentStorage
from app.ingestion.validators import validate_upload
from app.repositories.document import DocumentRepository
from app.repositories.profile import ProfileRepository
from app.services.audit import AuditService

logger = logging.getLogger("dr_robot.documents")


class DocumentService:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        repository: DocumentRepository | None = None,
        profiles: ProfileRepository | None = None,
        audit: AuditService | None = None,
        parser: DocumentParser | None = None,
        storage: LocalDocumentStorage | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        upload_root = Path(self.settings.upload_dir)
        if not upload_root.is_absolute():
            upload_root = REPOSITORY_ROOT / upload_root
        self.repository = repository or DocumentRepository()
        self.profiles = profiles or ProfileRepository()
        self.audit = audit or AuditService()
        self.parser = parser or DocumentParser()
        self.storage = storage or LocalDocumentStorage(upload_root)

    def _require_profile(self, db: Session, profile_id: str):
        profile = self.profiles.get(db, profile_id)
        if profile is None:
            raise ApiError(
                status_code=404,
                code="PROFILE_NOT_FOUND",
                message="Health profile was not found.",
            )
        return profile

    def _require_document(self, db: Session, document_id: str) -> SourceDocument:
        document = self.repository.get(db, document_id)
        if document is None:
            raise ApiError(
                status_code=404,
                code="DOCUMENT_NOT_FOUND",
                message="Source document was not found.",
            )
        return document

    def upload(
        self,
        db: Session,
        profile_id: str,
        *,
        stream: BinaryIO,
        filename: str,
        mime_type: str,
        document_date: date | None = None,
    ) -> SourceDocument:
        profile = self._require_profile(db, profile_id)
        upload = validate_upload(
            stream,
            filename=filename,
            declared_mime_type=mime_type,
            max_size_bytes=self.settings.max_upload_size_mb * 1024 * 1024,
        )
        duplicate = self.repository.find_duplicate(db, profile_id, upload.file_hash)
        if duplicate is not None:
            raise ApiError(
                status_code=409,
                code="DUPLICATE_DOCUMENT",
                message="This profile already contains an identical document.",
            )

        document_id = str(uuid4())
        stored = self.storage.store(profile_id, document_id, upload)
        document = SourceDocument(
            id=document_id,
            profile_id=profile_id,
            original_filename=upload.original_filename,
            stored_filename=stored.stored_filename,
            mime_type=upload.mime_type,
            file_hash=upload.file_hash,
            storage_path=stored.relative_path,
            document_date=document_date,
            status=DocumentStatus.UPLOADED,
            page_count=0,
        )
        try:
            self.repository.create(db, document)
            self.audit.append(
                db,
                action="DOCUMENT_UPLOADED",
                entity_type="source_document",
                entity_id=document.id,
                actor_user_id=profile.owner_user_id,
                after_state={
                    "profile_id": profile_id,
                    "mime_type": upload.mime_type,
                    "file_hash": upload.file_hash,
                    "status": DocumentStatus.UPLOADED.value,
                },
            )
            db.commit()
        except Exception:
            db.rollback()
            self.storage.remove(stored)
            raise

        document.status = DocumentStatus.PROCESSING
        db.commit()
        try:
            parsed = self.parser.parse(stored.absolute_path, upload.mime_type)
            document.extracted_text = parsed.full_text or None
            document.page_count = parsed.page_count
            document.status = parsed.status
            self.repository.replace_pages(db, document, parsed.pages)
            self.audit.append(
                db,
                action="DOCUMENT_PARSED",
                entity_type="source_document",
                entity_id=document.id,
                actor_user_id=profile.owner_user_id,
                after_state={
                    "status": parsed.status.value,
                    "page_count": parsed.page_count,
                    "has_extracted_text": bool(parsed.full_text),
                },
            )
            db.commit()
        except Exception:
            db.rollback()
            persisted = self._require_document(db, document.id)
            persisted.status = DocumentStatus.FAILED
            persisted.extracted_text = None
            persisted.page_count = 0
            self.audit.append(
                db,
                action="DOCUMENT_PARSE_FAILED",
                entity_type="source_document",
                entity_id=persisted.id,
                actor_user_id=profile.owner_user_id,
                after_state={"status": DocumentStatus.FAILED.value},
            )
            db.commit()
            logger.exception(
                "Document parsing failed",
                extra={"document_id": persisted.id, "mime_type": persisted.mime_type},
            )
            return persisted
        db.refresh(document)
        return document

    def list_documents(self, db: Session, profile_id: str) -> list[SourceDocument]:
        self._require_profile(db, profile_id)
        return self.repository.list_for_profile(db, profile_id)

    def get_document(self, db: Session, document_id: str) -> SourceDocument:
        return self._require_document(db, document_id)

    def list_pages(self, db: Session, document_id: str) -> list[DocumentPage]:
        self._require_document(db, document_id)
        return self.repository.list_pages(db, document_id)


def get_document_service() -> DocumentService:
    return DocumentService()
