"""Profile-scoped trusted timeline and evidence endpoints."""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.timeline.evidence import EvidenceService
from app.timeline.missing_evidence import MissingEvidenceService
from app.timeline.schemas import (
    EvidenceResponse,
    MissingEvidenceResponse,
    TimelineEntityType,
    TimelineResponse,
    TimelineType,
)
from app.timeline.service import TimelineService

router = APIRouter(tags=["timeline"])


@router.get("/profiles/{profile_id}/timeline", response_model=TimelineResponse)
def get_timeline(
    profile_id: str,
    db: Annotated[Session, Depends(get_db)],
    sort: Literal["asc", "desc"] = "desc",
    timeline_type: Annotated[TimelineType | None, Query(alias="type")] = None,
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TimelineResponse:
    return TimelineService().list(
        db,
        profile_id,
        sort=sort,
        timeline_type=timeline_type,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/profiles/{profile_id}/evidence/gaps",
    response_model=MissingEvidenceResponse,
)
def get_missing_evidence(
    profile_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> MissingEvidenceResponse:
    return MissingEvidenceService().list(db, profile_id)


@router.get(
    "/profiles/{profile_id}/evidence/{entity_type}/{entity_id}",
    response_model=EvidenceResponse,
)
def get_evidence(
    profile_id: str,
    entity_type: TimelineEntityType,
    entity_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> EvidenceResponse:
    return EvidenceService().resolve(db, profile_id, entity_type, entity_id)
