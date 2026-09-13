"""Health-profile persistence operations."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import HealthProfile
from app.schemas.profile import ProfileCreate


class ProfileRepository:
    def create(self, db: Session, data: ProfileCreate) -> HealthProfile:
        profile = HealthProfile(**data.model_dump())
        db.add(profile)
        db.flush()
        return profile

    def get(self, db: Session, profile_id: str) -> HealthProfile | None:
        return db.get(HealthProfile, profile_id)

    def list(self, db: Session) -> list[HealthProfile]:
        statement = select(HealthProfile).order_by(HealthProfile.display_name, HealthProfile.id)
        return list(db.scalars(statement))

    def update(
        self, db: Session, profile: HealthProfile, changes: dict[str, object]
    ) -> HealthProfile:
        for field, value in changes.items():
            setattr(profile, field, value)
        db.flush()
        return profile
