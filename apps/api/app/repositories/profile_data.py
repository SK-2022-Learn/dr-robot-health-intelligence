"""Focused read queries for profile-owned Phase 3 UI data."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import (
    Medication,
    Observation,
    SourceDocument,
    Symptom,
)


class ProfileDataRepository:
    def list_observations(self, db: Session, profile_id: str) -> list[Observation]:
        statement = (
            select(Observation)
            .where(Observation.profile_id == profile_id)
            .order_by(Observation.observed_at.desc(), Observation.id)
        )
        return list(db.scalars(statement))

    def list_medications(self, db: Session, profile_id: str) -> list[Medication]:
        statement = (
            select(Medication)
            .where(Medication.profile_id == profile_id)
            .order_by(Medication.is_active.desc(), Medication.start_date.desc(), Medication.id)
        )
        return list(db.scalars(statement))

    def list_symptoms(self, db: Session, profile_id: str) -> list[Symptom]:
        statement = (
            select(Symptom)
            .where(Symptom.profile_id == profile_id)
            .order_by(Symptom.started_at.desc(), Symptom.id)
        )
        return list(db.scalars(statement))

    def list_documents(self, db: Session, profile_id: str) -> list[SourceDocument]:
        statement = (
            select(SourceDocument)
            .where(SourceDocument.profile_id == profile_id)
            .order_by(SourceDocument.document_date.desc(), SourceDocument.created_at.desc())
        )
        return list(db.scalars(statement))
