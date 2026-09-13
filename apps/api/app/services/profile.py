"""Health-profile business rules and audited trusted-data changes."""

from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.database.models import HealthProfile
from app.repositories.profile import ProfileRepository
from app.repositories.user import UserRepository
from app.schemas.profile import ProfileCreate, ProfileRead, ProfileUpdate
from app.services.audit import AuditService


def _profile_state(profile: HealthProfile) -> dict[str, object]:
    return ProfileRead.model_validate(profile).model_dump(mode="json")


class ProfileService:
    def __init__(
        self,
        repository: ProfileRepository | None = None,
        users: UserRepository | None = None,
        audit: AuditService | None = None,
    ) -> None:
        self.repository = repository or ProfileRepository()
        self.users = users or UserRepository()
        self.audit = audit or AuditService()

    def create_profile(self, db: Session, data: ProfileCreate) -> HealthProfile:
        if self.users.get(db, data.owner_user_id) is None:
            raise ApiError(
                status_code=404, code="USER_NOT_FOUND", message="Profile owner was not found."
            )

        profile = self.repository.create(db, data)
        # Trusted profile changes and their audit evidence commit atomically.
        self.audit.append(
            db,
            action="profile.created",
            entity_type="health_profile",
            entity_id=profile.id,
            actor_user_id=data.owner_user_id,
            after_state=_profile_state(profile),
        )
        db.commit()
        db.refresh(profile)
        return profile

    def retrieve_profile(self, db: Session, profile_id: str) -> HealthProfile:
        profile = self.repository.get(db, profile_id)
        if profile is None:
            raise ApiError(
                status_code=404,
                code="PROFILE_NOT_FOUND",
                message="Health profile was not found.",
            )
        return profile

    def list_profiles(self, db: Session) -> list[HealthProfile]:
        return self.repository.list(db)

    def update_profile(self, db: Session, profile_id: str, data: ProfileUpdate) -> HealthProfile:
        profile = self.retrieve_profile(db, profile_id)
        before_state = _profile_state(profile)
        changes = data.model_dump(exclude_unset=True, exclude_none=True)
        if not changes:
            return profile

        profile = self.repository.update(db, profile, changes)
        self.audit.append(
            db,
            action="profile.updated",
            entity_type="health_profile",
            entity_id=profile.id,
            actor_user_id=profile.owner_user_id,
            before_state=before_state,
            after_state=_profile_state(profile),
        )
        db.commit()
        db.refresh(profile)
        return profile
