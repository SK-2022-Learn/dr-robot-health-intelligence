"""Document indexing and profile-scoped semantic retrieval endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.retrieval.service import (
    RetrievalIndexService,
    RetrievalService,
    get_retrieval_index_service,
    get_retrieval_service,
)
from app.schemas.retrieval import (
    DocumentIndexSummary,
    RetrievalSearchRequest,
    RetrievalSearchResponse,
)

router = APIRouter(tags=["retrieval"])


@router.post("/documents/{document_id}/index", response_model=DocumentIndexSummary)
def index_document(
    document_id: str,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[RetrievalIndexService, Depends(get_retrieval_index_service)],
) -> DocumentIndexSummary:
    return service.index_document(db, document_id)


@router.post(
    "/profiles/{profile_id}/retrieval/search",
    response_model=RetrievalSearchResponse,
)
def semantic_search(
    profile_id: str,
    request: RetrievalSearchRequest,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[RetrievalService, Depends(get_retrieval_service)],
) -> RetrievalSearchResponse:
    return service.search(db, profile_id, request.query.strip(), request.top_k)
