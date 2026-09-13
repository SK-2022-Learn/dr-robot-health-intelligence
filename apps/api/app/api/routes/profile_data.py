"""Read-only endpoints for profile data displayed in Phase 3."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.document import SourceDocumentSummary
from app.schemas.medication import MedicationRead
from app.schemas.observation import ObservationRead
from app.schemas.symptom import SymptomRead
from app.services.document import DocumentService
from app.services.profile_data import ProfileDataService

router = APIRouter(tags=["profile data"])
service = ProfileDataService()
document_service = DocumentService()


@router.get("/profiles/{profile_id}/observations", response_model=list[ObservationRead])
def list_observations(profile_id: str, db: Annotated[Session, Depends(get_db)]) -> object:
    return service.observations(db, profile_id)


@router.get("/profiles/{profile_id}/medications", response_model=list[MedicationRead])
def list_medications(profile_id: str, db: Annotated[Session, Depends(get_db)]) -> object:
    return service.medications(db, profile_id)


@router.get("/profiles/{profile_id}/symptoms", response_model=list[SymptomRead])
def list_symptoms(profile_id: str, db: Annotated[Session, Depends(get_db)]) -> object:
    return service.symptoms(db, profile_id)


@router.get("/profiles/{profile_id}/documents", response_model=list[SourceDocumentSummary])
def list_documents(profile_id: str, db: Annotated[Session, Depends(get_db)]) -> object:
    return document_service.list_documents(db, profile_id)
