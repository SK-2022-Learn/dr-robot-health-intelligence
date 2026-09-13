"""Observation persistence operations."""

from datetime import date, datetime, time

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database.enums import VerificationStatus
from app.database.models import Observation
from app.schemas.observation import ObservationCreate


class ObservationRepository:
    def create(self, db: Session, data: ObservationCreate) -> Observation:
        observation = Observation(**data.model_dump())
        db.add(observation)
        db.flush()
        return observation

    def get(self, db: Session, observation_id: str) -> Observation | None:
        return db.get(Observation, observation_id)

    def list_trusted_in_range(
        self,
        db: Session,
        profile_id: str,
        from_date: date,
        to_date: date,
    ) -> list[Observation]:
        """Return verified, potentially numeric observations inside an inclusive date range."""

        statement = (
            select(Observation)
            .where(
                Observation.profile_id == profile_id,
                Observation.verification_status == VerificationStatus.VERIFIED,
                Observation.observed_at >= datetime.combine(from_date, time.min),
                Observation.observed_at <= datetime.combine(to_date, time.max),
                or_(Observation.value_number.is_not(None), Observation.value_text.is_not(None)),
            )
            .order_by(Observation.observed_at, Observation.id)
        )
        return list(db.scalars(statement))
