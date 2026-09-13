"""Permission-aware family graph, patterns, evidence, and consent APIs."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.family.schemas import (
    FamilyGraphResponse,
    FamilyPatternsResponse,
    FamilyPermissionRead,
    FamilyPermissionUpdate,
)
from app.family.service import FamilyService

router = APIRouter(prefix="/family", tags=["family intelligence"])
service = FamilyService()


@router.get("", response_model=FamilyGraphResponse)
def get_family(
    selected_profile_id: Annotated[str, Query(min_length=1)],
    requester_user_id: Annotated[str, Query(min_length=1)],
    db: Annotated[Session, Depends(get_db)],
) -> FamilyGraphResponse:
    return service.graph(db, selected_profile_id, requester_user_id)


@router.get("/patterns", response_model=FamilyPatternsResponse)
def get_patterns(
    selected_profile_id: Annotated[str, Query(min_length=1)],
    requester_user_id: Annotated[str, Query(min_length=1)],
    db: Annotated[Session, Depends(get_db)],
    condition: str | None = None,
    branch: str | None = None,
) -> FamilyPatternsResponse:
    return service.pattern_results(
        db,
        selected_profile_id,
        requester_user_id,
        condition=condition,
        branch=branch,
    )


@router.get("/shared-conditions", response_model=FamilyPatternsResponse)
def get_shared_conditions(
    selected_profile_id: Annotated[str, Query(min_length=1)],
    requester_user_id: Annotated[str, Query(min_length=1)],
    db: Annotated[Session, Depends(get_db)],
) -> FamilyPatternsResponse:
    return service.pattern_results(db, selected_profile_id, requester_user_id)


@router.get("/patterns/{condition}/contributors", response_model=FamilyPatternsResponse)
def get_contributors(
    condition: str,
    selected_profile_id: Annotated[str, Query(min_length=1)],
    requester_user_id: Annotated[str, Query(min_length=1)],
    db: Annotated[Session, Depends(get_db)],
) -> FamilyPatternsResponse:
    return service.pattern_results(db, selected_profile_id, requester_user_id, condition=condition)


@router.patch("/permissions/{permission_id}", response_model=FamilyPermissionRead)
def update_permission(
    permission_id: str,
    data: FamilyPermissionUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> FamilyPermissionRead:
    return service.update_permission(db, permission_id, data.requester_user_id, data.access_level)
