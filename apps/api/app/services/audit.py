"""Append-only audit coordination."""

from typing import Any

from sqlalchemy.orm import Session

from app.database.models import AuditLog
from app.repositories.audit import AuditRepository


class AuditService:
    def __init__(self, repository: AuditRepository | None = None) -> None:
        self.repository = repository or AuditRepository()

    def append(
        self,
        db: Session,
        *,
        action: str,
        entity_type: str,
        entity_id: str,
        actor_user_id: str | None = None,
        before_state: dict[str, Any] | None = None,
        after_state: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Append within the caller's transaction; audit rows are never mutated."""

        return self.repository.append(
            db,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_user_id=actor_user_id,
            before_state=before_state,
            after_state=after_state,
        )

    def list(
        self,
        db: Session,
        *,
        entity_type: str | None = None,
        entity_id: str | None = None,
    ) -> list[AuditLog]:
        return self.repository.list(db, entity_type=entity_type, entity_id=entity_id)
