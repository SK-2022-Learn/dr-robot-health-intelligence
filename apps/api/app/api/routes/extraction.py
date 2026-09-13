"""Document extraction and candidate-review endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.enums import CandidateStatus
from app.database.session import get_db
from app.extraction.service import ExtractionService, get_extraction_service
from app.schemas.candidate import (
    CandidateCorrectionRequest,
    CandidateDetail,
    CandidateReviewResult,
    ExtractionSummary,
)

router = APIRouter(tags=["extraction"])


@router.post("/documents/{document_id}/extract", response_model=ExtractionSummary)
def extract_document(
    document_id: str,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[ExtractionService, Depends(get_extraction_service)],
) -> ExtractionSummary:
    return service.extract(db, document_id)


@router.get("/documents/{document_id}/candidates", response_model=list[CandidateDetail])
def list_candidates(
    document_id: str,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[ExtractionService, Depends(get_extraction_service)],
    candidate_status: Annotated[CandidateStatus | None, Query(alias="status")] = None,
) -> list[CandidateDetail]:
    return service.list_candidates(db, document_id, candidate_status)


@router.post("/candidates/{candidate_id}/accept", response_model=CandidateReviewResult)
def accept_candidate(
    candidate_id: str,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[ExtractionService, Depends(get_extraction_service)],
) -> CandidateReviewResult:
    return service.accept(db, candidate_id)


@router.patch("/candidates/{candidate_id}/correct", response_model=CandidateReviewResult)
def correct_candidate(
    candidate_id: str,
    correction: CandidateCorrectionRequest,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[ExtractionService, Depends(get_extraction_service)],
) -> CandidateReviewResult:
    return service.correct(db, candidate_id, correction)


@router.post("/candidates/{candidate_id}/reject", response_model=CandidateReviewResult)
def reject_candidate(
    candidate_id: str,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[ExtractionService, Depends(get_extraction_service)],
) -> CandidateReviewResult:
    return service.reject(db, candidate_id)
