"""Persistence for immutable extraction candidates and review state."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.enums import CandidateStatus
from app.database.models import ExtractedCandidate


class CandidateRepository:
    def get(self, db: Session, candidate_id: str) -> ExtractedCandidate | None:
        return db.get(ExtractedCandidate, candidate_id)

    def create(self, db: Session, candidate: ExtractedCandidate) -> ExtractedCandidate:
        db.add(candidate)
        db.flush()
        return candidate

    def list_for_document(
        self,
        db: Session,
        document_id: str,
        status: CandidateStatus | None = None,
    ) -> list[ExtractedCandidate]:
        statement = select(ExtractedCandidate).where(ExtractedCandidate.document_id == document_id)
        if status is not None:
            statement = statement.where(ExtractedCandidate.status == status)
        return list(
            db.scalars(statement.order_by(ExtractedCandidate.created_at, ExtractedCandidate.id))
        )
