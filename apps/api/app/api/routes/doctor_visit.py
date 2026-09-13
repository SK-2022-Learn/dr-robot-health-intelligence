"""Profile-scoped Doctor Visit brief generation."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.doctor_visit.schemas import DoctorVisitBrief
from app.doctor_visit.service import DoctorVisitService, get_doctor_visit_service

router = APIRouter(tags=["doctor visit"])


@router.post(
    "/profiles/{profile_id}/doctor-visit/generate",
    response_model=DoctorVisitBrief,
)
def generate_doctor_visit_brief(
    profile_id: str,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[DoctorVisitService, Depends(get_doctor_visit_service)],
    recent_days: Annotated[int, Query(ge=1, le=365)] = 30,
    max_labs: Annotated[int, Query(ge=1, le=20)] = 5,
    max_measurements: Annotated[int, Query(ge=1, le=30)] = 8,
    max_symptoms: Annotated[int, Query(ge=1, le=20)] = 5,
    include_llm_rewrite: bool = False,
) -> DoctorVisitBrief:
    """POST is intentional because every generated brief appends an audit event."""

    return service.generate(
        db,
        profile_id,
        recent_days=recent_days,
        max_labs=max_labs,
        max_measurements=max_measurements,
        max_symptoms=max_symptoms,
        include_llm_rewrite=include_llm_rewrite,
    )
