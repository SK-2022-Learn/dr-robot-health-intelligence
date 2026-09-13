"""Longitudinal health-event persistence operations."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import HealthEvent
from app.schemas.health_event import HealthEventCreate


class HealthEventRepository:
    def create(self, db: Session, profile_id: str, data: HealthEventCreate) -> HealthEvent:
        health_event = HealthEvent(profile_id=profile_id, **data.model_dump())
        db.add(health_event)
        db.flush()
        return health_event

    def get(self, db: Session, event_id: str) -> HealthEvent | None:
        return db.get(HealthEvent, event_id)

    def list_for_profile(self, db: Session, profile_id: str) -> list[HealthEvent]:
        statement = (
            select(HealthEvent)
            .where(HealthEvent.profile_id == profile_id)
            .order_by(HealthEvent.event_date.desc(), HealthEvent.id)
        )
        return list(db.scalars(statement))

    def update(self, db: Session, event: HealthEvent, changes: dict[str, object]) -> HealthEvent:
        for field, value in changes.items():
            setattr(event, field, value)
        db.flush()
        return event
