"""Index parsed documents and retrieve profile-isolated source evidence."""

import logging
from typing import Annotated, Any

from fastapi import Depends
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.errors import ApiError
from app.database.base import utc_now
from app.database.enums import DocumentStatus, VectorIndexStatus
from app.database.models import SourceDocument
from app.embeddings.base import EmbeddingProvider
from app.embeddings.factory import get_embedding_provider
from app.embeddings.types import EmbeddingError, EmbeddingUnavailableError
from app.repositories.document import DocumentRepository
from app.repositories.profile import ProfileRepository
from app.retrieval.chunking import chunk_document_pages
from app.schemas.retrieval import (
    DocumentIndexSummary,
    EvidenceContext,
    RetrievalSearchResponse,
)
from app.services.audit import AuditService
from app.vectorstore.base import VectorStoreProvider
from app.vectorstore.factory import get_vector_store_provider
from app.vectorstore.types import VectorRecord, VectorStoreUnavailableError

logger = logging.getLogger("dr_robot.retrieval")


class RetrievalIndexService:
    def __init__(
        self,
        vector_store: VectorStoreProvider,
        embeddings: EmbeddingProvider,
        *,
        settings: Settings | None = None,
        documents: DocumentRepository | None = None,
        audit: AuditService | None = None,
    ) -> None:
        self.vector_store = vector_store
        self.embeddings = embeddings
        self.settings = settings or get_settings()
        self.documents = documents or DocumentRepository()
        self.audit = audit or AuditService()

    def _require_document(self, db: Session, document_id: str) -> SourceDocument:
        document = self.documents.get(db, document_id)
        if document is None:
            raise ApiError(
                status_code=404,
                code="DOCUMENT_NOT_FOUND",
                message="Source document was not found.",
            )
        if document.status != DocumentStatus.PARSED or not document.has_extracted_text:
            raise ApiError(
                status_code=422,
                code="DOCUMENT_NOT_PARSED",
                message="The document must contain parsed text before indexing.",
            )
        return document

    def _mark_failed(self, db: Session, document: SourceDocument, error_code: str) -> None:
        db.rollback()
        persisted = self.documents.get(db, document.id)
        if persisted is None:
            return
        persisted.vector_index_status = VectorIndexStatus.INDEX_FAILED
        persisted.vector_index_error = error_code
        persisted.vector_indexed_at = None
        persisted.vector_chunk_count = 0
        self.audit.append(
            db,
            action="DOCUMENT_INDEXING_FAILED",
            entity_type="source_document",
            entity_id=persisted.id,
            actor_user_id=persisted.profile.owner_user_id,
            after_state={"error_code": error_code},
        )
        db.commit()

    def index_document(self, db: Session, document_id: str) -> DocumentIndexSummary:
        document = self._require_document(db, document_id)
        document.vector_index_status = VectorIndexStatus.INDEXING
        document.vector_index_error = None
        self.audit.append(
            db,
            action="DOCUMENT_INDEXING_STARTED",
            entity_type="source_document",
            entity_id=document.id,
            actor_user_id=document.profile.owner_user_id,
            after_state={"profile_id": document.profile_id},
        )
        db.commit()

        try:
            pages = self.documents.list_pages(db, document.id)
            chunks = chunk_document_pages(
                document,
                pages,
                chunk_size=self.settings.chunk_size_chars,
                overlap=self.settings.chunk_overlap_chars,
            )
            if not chunks:
                raise ApiError(
                    status_code=422,
                    code="NO_INDEXABLE_TEXT",
                    message="No page text was available for semantic indexing.",
                )
            vectors = self.embeddings.embed_batch([chunk.text for chunk in chunks])
            index_info = self.vector_store.get_index_info()
            dimensions = {len(vector) for vector in vectors}
            if len(dimensions) != 1 or index_info.dimension not in dimensions:
                raise ApiError(
                    status_code=409,
                    code="VECTOR_DIMENSION_MISMATCH",
                    message="Embedding and vector index dimensions are incompatible.",
                )
            records: list[VectorRecord] = []
            for chunk, vector in zip(chunks, vectors, strict=True):
                metadata: dict[str, Any] = {**chunk.metadata, "text": chunk.text}
                if document.document_date is not None:
                    metadata["document_date"] = document.document_date.isoformat()
                records.append(VectorRecord(chunk.chunk_id, vector, metadata))
            self.vector_store.delete_document(document.id, document.profile_id)
            inserted = self.vector_store.upsert_chunks(document.profile_id, records)
            if inserted != len(records):
                raise VectorStoreUnavailableError("Pinecone did not confirm every vector.")
        except ApiError as error:
            self._mark_failed(db, document, error.code)
            raise
        except EmbeddingUnavailableError as error:
            self._mark_failed(db, document, "EMBEDDING_PROVIDER_UNAVAILABLE")
            raise ApiError(
                status_code=503,
                code="EMBEDDING_PROVIDER_UNAVAILABLE",
                message="The embedding provider is currently unavailable.",
            ) from error
        except EmbeddingError as error:
            self._mark_failed(db, document, "EMBEDDING_FAILED")
            raise ApiError(
                status_code=502,
                code="EMBEDDING_FAILED",
                message="Document embeddings could not be generated.",
            ) from error
        except VectorStoreUnavailableError as error:
            self._mark_failed(db, document, "VECTOR_STORE_UNAVAILABLE")
            raise ApiError(
                status_code=503,
                code="VECTOR_STORE_UNAVAILABLE",
                message="Semantic retrieval is currently unavailable.",
            ) from error
        except Exception as error:
            self._mark_failed(db, document, "INDEXING_FAILED")
            logger.exception(
                "Unexpected document indexing failure", extra={"document_id": document.id}
            )
            raise ApiError(
                status_code=502,
                code="DOCUMENT_INDEXING_FAILED",
                message="The document could not be indexed for search.",
            ) from error

        document.vector_index_status = VectorIndexStatus.INDEXED
        document.vector_indexed_at = utc_now()
        document.vector_chunk_count = len(records)
        document.vector_index_error = None
        self.audit.append(
            db,
            action="DOCUMENT_INDEXING_COMPLETED",
            entity_type="source_document",
            entity_id=document.id,
            actor_user_id=document.profile.owner_user_id,
            after_state={"chunk_count": len(records), "profile_id": document.profile_id},
        )
        db.commit()
        return DocumentIndexSummary(
            document_id=document.id,
            status=document.vector_index_status,
            chunk_count=document.vector_chunk_count,
        )


class RetrievalService:
    def __init__(
        self,
        vector_store: VectorStoreProvider,
        embeddings: EmbeddingProvider,
        *,
        documents: DocumentRepository | None = None,
        profiles: ProfileRepository | None = None,
        audit: AuditService | None = None,
    ) -> None:
        self.vector_store = vector_store
        self.embeddings = embeddings
        self.documents = documents or DocumentRepository()
        self.profiles = profiles or ProfileRepository()
        self.audit = audit or AuditService()

    def search(
        self, db: Session, profile_id: str, query: str, top_k: int
    ) -> RetrievalSearchResponse:
        profile = self.profiles.get(db, profile_id)
        if profile is None:
            raise ApiError(
                status_code=404,
                code="PROFILE_NOT_FOUND",
                message="Health profile was not found.",
            )
        indexed_count = self.documents.indexed_count_for_profile(db, profile_id)
        if indexed_count == 0:
            self.audit.append(
                db,
                action="SEMANTIC_SEARCH_EXECUTED",
                entity_type="health_profile",
                entity_id=profile_id,
                actor_user_id=profile.owner_user_id,
                after_state={"profile_id": profile_id, "result_count": 0, "top_k": top_k},
            )
            db.commit()
            return RetrievalSearchResponse(
                query=query,
                results=[],
                indexed_document_count=0,
            )
        try:
            query_vector = self.embeddings.embed_text(query)
            matches = self.vector_store.query(profile_id, query_vector, top_k)
        except EmbeddingError as error:
            raise ApiError(
                status_code=503,
                code="EMBEDDING_PROVIDER_UNAVAILABLE",
                message="The embedding provider is currently unavailable.",
            ) from error
        except VectorStoreUnavailableError as error:
            raise ApiError(
                status_code=503,
                code="VECTOR_STORE_UNAVAILABLE",
                message="Semantic retrieval is currently unavailable.",
            ) from error

        results: list[EvidenceContext] = []
        for match in matches:
            metadata = match.metadata
            try:
                document_id = str(metadata["document_id"])
                page_number = int(metadata["page_number"])
                chunk_index = int(metadata["chunk_index"])
                text = str(metadata["text"])
            except (KeyError, TypeError, ValueError):
                logger.warning(
                    "Excluded vector result with invalid metadata",
                    extra={"vector_id": match.id, "profile_id": profile_id},
                )
                continue
            document = self.documents.get(db, document_id)
            page = self.documents.get_page(db, document_id, page_number)
            if (
                document is None
                or document.profile_id != profile_id
                or document.vector_index_status != VectorIndexStatus.INDEXED
                or page is None
                or text not in page.text
            ):
                logger.warning(
                    "Excluded vector result that failed local source validation",
                    extra={"vector_id": match.id, "profile_id": profile_id},
                )
                continue
            results.append(
                EvidenceContext(
                    score=match.score,
                    document_id=document.id,
                    filename=document.original_filename,
                    page_number=page_number,
                    text=text,
                    chunk_index=chunk_index,
                )
            )
        self.audit.append(
            db,
            action="SEMANTIC_SEARCH_EXECUTED",
            entity_type="health_profile",
            entity_id=profile_id,
            actor_user_id=profile.owner_user_id,
            after_state={"profile_id": profile_id, "result_count": len(results), "top_k": top_k},
        )
        db.commit()
        return RetrievalSearchResponse(
            query=query,
            results=results,
            indexed_document_count=indexed_count,
        )


def get_retrieval_index_service(
    vector_store: Annotated[VectorStoreProvider, Depends(get_vector_store_provider)],
    embeddings: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
) -> RetrievalIndexService:
    return RetrievalIndexService(vector_store, embeddings)


def get_retrieval_service(
    vector_store: Annotated[VectorStoreProvider, Depends(get_vector_store_provider)],
    embeddings: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
) -> RetrievalService:
    return RetrievalService(vector_store, embeddings)
