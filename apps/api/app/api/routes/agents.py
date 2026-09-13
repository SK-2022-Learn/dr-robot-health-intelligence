"""Unified, profile-scoped Ask Dr. Robot endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.schemas import AskRequest, AskResponse
from app.agents.service import AgentService, get_agent_service
from app.database.session import get_db

router = APIRouter(tags=["agent orchestration"])


@router.post("/profiles/{profile_id}/ask", response_model=AskResponse)
def ask_dr_robot(
    profile_id: str,
    request: AskRequest,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[AgentService, Depends(get_agent_service)],
) -> AskResponse:
    """Route a request without granting the graph direct trusted-memory writes."""

    return service.ask(db, profile_id, request)
