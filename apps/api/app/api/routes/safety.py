"""Development endpoint for deterministic safety-policy evaluation."""

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.safety.schemas import SafetyInput, SafetyResult
from app.safety.service import SafetyService, get_safety_service

router = APIRouter(prefix="/safety", tags=["safety"])


@router.post("/evaluate", response_model=SafetyResult)
def evaluate_safety(
    data: SafetyInput,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[SafetyService, Depends(get_safety_service)],
) -> SafetyResult:
    """Evaluate policy without returning or auditing sensitive input text."""

    result = service.evaluate(data)
    service.audit_result(
        db,
        result,
        entity_id=str(uuid4()),
        profile_id=data.profile_id,
    )
    db.commit()
    return result
