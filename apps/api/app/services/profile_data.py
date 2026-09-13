"""Profile-isolated read services for the connected UI."""

from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.database.models import (
    HealthProfile,
    Medication,
    Observation,
    SourceDocument,
    Symptom,
)
from app.repositories.profile import ProfileRepository
from app.repositories.profile_data import ProfileDataRepository


class ProfileDataService:
    def __init__(
        self,
        repository: ProfileDataRepository | None = None,
        profiles: ProfileRepository | None = None,
    ) -> None:
        self.repository = repository or ProfileDataRepository()
        self.profiles = profiles or ProfileRepository()

    def require_profile(self, db: Session, profile_id: str) -> HealthProfile:
        profile = self.profiles.get(db, profile_id)
        if profile is None:
            raise ApiError(
                status_code=404,
                code="PROFILE_NOT_FOUND",
                message="Health profile was not found.",
            )
        return profile

    def observations(self, db: Session, profile_id: str) -> list[Observation]:
        self.require_profile(db, profile_id)
        return self.repository.list_observations(db, profile_id)

    def medications(self, db: Session, profile_id: str) -> list[Medication]:
        self.require_profile(db, profile_id)
        return self.repository.list_medications(db, profile_id)

    def symptoms(self, db: Session, profile_id: str) -> list[Symptom]:
        self.require_profile(db, profile_id)
        return self.repository.list_symptoms(db, profile_id)

    def documents(self, db: Session, profile_id: str) -> list[SourceDocument]:
        self.require_profile(db, profile_id)
        return self.repository.list_documents(db, profile_id)
