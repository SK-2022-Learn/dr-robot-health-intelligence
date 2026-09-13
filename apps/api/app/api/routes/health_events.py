"""Minimal Phase 2 longitudinal health-event APIs."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.health_event import HealthEventCreate, HealthEventRead, HealthEventUpdate
from app.services.health_event import HealthEventService

router = APIRouter(tags=["health events"])
service = HealthEventService()


@router.post(
    "/profiles/{profile_id}/events",
    response_model=HealthEventRead,
    status_code=status.HTTP_201_CREATED,
)
def create_event(
    profile_id: str,
    data: HealthEventCreate,
    db: Annotated[Session, Depends(get_db)],
) -> object:
    return service.create_event(db, profile_id, data)


@router.get("/profiles/{profile_id}/events", response_model=list[HealthEventRead])
def list_events(profile_id: str, db: Annotated[Session, Depends(get_db)]) -> object:
    return service.list_profile_events(db, profile_id)


@router.get("/events/{event_id}", response_model=HealthEventRead)
def get_event(event_id: str, db: Annotated[Session, Depends(get_db)]) -> object:
    return service.retrieve_event(db, event_id)


@router.patch("/events/{event_id}", response_model=HealthEventRead)
def update_event(
    event_id: str,
    data: HealthEventUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> object:
    return service.update_event(db, event_id, data)
