"""Read-only access to append-only audit history."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.audit import AuditRead
from app.services.audit import AuditService

router = APIRouter(prefix="/audit", tags=["audit"])
service = AuditService()


@router.get("", response_model=list[AuditRead])
def list_audit_logs(
    db: Annotated[Session, Depends(get_db)],
    entity_type: Annotated[str | None, Query(max_length=100)] = None,
    entity_id: Annotated[str | None, Query(max_length=36)] = None,
) -> object:
    return service.list(db, entity_type=entity_type, entity_id=entity_id)
