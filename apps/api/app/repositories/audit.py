"""Append-only audit-log persistence and read operations."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import AuditLog


class AuditRepository:
    """Audit history intentionally exposes no update or delete operation."""

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
        audit_log = AuditLog(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_user_id=actor_user_id,
            before_state=before_state,
            after_state=after_state,
        )
        db.add(audit_log)
        db.flush()
        return audit_log

    def list(
        self,
        db: Session,
        *,
        entity_type: str | None = None,
        entity_id: str | None = None,
    ) -> list[AuditLog]:
        statement = select(AuditLog)
        if entity_type:
            statement = statement.where(AuditLog.entity_type == entity_type)
        if entity_id:
            statement = statement.where(AuditLog.entity_id == entity_id)
        return list(db.scalars(statement.order_by(AuditLog.created_at.desc(), AuditLog.id)))
