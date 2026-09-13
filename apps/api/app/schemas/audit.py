"""Read-only audit-log response contracts."""

from datetime import datetime
from typing import Any

from app.schemas.common import SchemaModel


class AuditRead(SchemaModel):
    id: str
    actor_user_id: str | None
    action: str
    entity_type: str
    entity_id: str
    before_state: dict[str, Any] | None
    after_state: dict[str, Any] | None
    created_at: datetime
