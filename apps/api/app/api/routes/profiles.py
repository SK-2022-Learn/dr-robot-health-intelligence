"""Minimal Phase 2 profile APIs using the service layer."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.profile import ProfileCreate, ProfileRead, ProfileUpdate
from app.services.profile import ProfileService

router = APIRouter(prefix="/profiles", tags=["profiles"])
service = ProfileService()


@router.post("", response_model=ProfileRead, status_code=status.HTTP_201_CREATED)
def create_profile(data: ProfileCreate, db: Annotated[Session, Depends(get_db)]) -> object:
    return service.create_profile(db, data)


@router.get("", response_model=list[ProfileRead])
def list_profiles(db: Annotated[Session, Depends(get_db)]) -> object:
    return service.list_profiles(db)


@router.get("/{profile_id}", response_model=ProfileRead)
def get_profile(profile_id: str, db: Annotated[Session, Depends(get_db)]) -> object:
    return service.retrieve_profile(db, profile_id)


@router.patch("/{profile_id}", response_model=ProfileRead)
def update_profile(
    profile_id: str, data: ProfileUpdate, db: Annotated[Session, Depends(get_db)]
) -> object:
    return service.update_profile(db, profile_id, data)
