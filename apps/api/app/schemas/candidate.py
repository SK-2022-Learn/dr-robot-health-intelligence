"""Untrusted extraction-candidate contracts for later review workflows."""

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from app.database.enums import CandidateStatus, CandidateType
from app.schemas.common import IdentityTimestamps, SchemaModel


class CandidateCreate(SchemaModel):
    document_id: str
    candidate_type: str
    raw_text: str
    structured_data: dict[str, Any]
    confidence: float | None = Field(default=None, ge=0, le=1)
    status: CandidateStatus = CandidateStatus.PENDING


class CandidateUpdate(SchemaModel):
    structured_data: dict[str, Any] | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    status: CandidateStatus | None = None
    reviewed_by_user_id: str | None = None
    reviewed_at: datetime | None = None


class CandidateRead(IdentityTimestamps, CandidateCreate):
    reviewed_by_user_id: str | None
    reviewed_at: datetime | None


class ExtractionSummary(SchemaModel):
    document_id: str
    status: Literal["completed"] = "completed"
    candidate_count: int
    by_type: dict[str, int]
    reused_existing: bool = False


class CandidateDetail(IdentityTimestamps):
    document_id: str
    candidate_type: CandidateType
    structured_data: dict[str, Any]
    confidence: float
    status: CandidateStatus
    evidence_text: str
    page_number: int | None
    reviewed_by_user_id: str | None
    reviewed_at: datetime | None


class CandidateCorrectionRequest(SchemaModel):
    structured_data: dict[str, Any]


class TrustedRecordReference(SchemaModel):
    record_type: str
    record_id: str


class CandidateReviewResult(SchemaModel):
    candidate: CandidateDetail
    trusted_record: TrustedRecordReference | None
