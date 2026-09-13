"""Centralized consent rules for every cross-profile family query."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.database.enums import AccessLevel, RelationshipType
from app.database.models import ConsentPermission, HealthProfile


@dataclass(frozen=True)
class PermissionDecision:
    access_level: AccessLevel
    permission_id: str | None

    @property
    def may_view_summary(self) -> bool:
        return self.access_level is not AccessLevel.PRIVATE

    @property
    def may_view_details(self) -> bool:
        return self.access_level in {AccessLevel.CAREGIVER, AccessLevel.FULL}


class PermissionService:
    """Resolve one effective access level without route-specific exceptions.

    The requester's SELF profile is always FULL. For another profile, the newest
    explicit user grant wins; `HealthProfile.access_level` remains a legacy
    fallback for existing Phase 2 data that predates consent rows.
    """

    def require_family_anchor(
        self, db: Session, selected_profile_id: str, requester_user_id: str
    ) -> HealthProfile:
        profile = db.get(HealthProfile, selected_profile_id)
        if profile is None:
            raise ApiError(
                status_code=404,
                code="PROFILE_NOT_FOUND",
                message="Health profile was not found.",
            )
        if profile.owner_user_id != requester_user_id:
            raise ApiError(
                status_code=403,
                code="FAMILY_ACCESS_DENIED",
                message="The requester cannot access this family.",
            )
        return profile

    def decision(
        self, db: Session, profile: HealthProfile, requester_user_id: str
    ) -> PermissionDecision:
        if (
            profile.owner_user_id == requester_user_id
            and profile.relationship_to_owner is RelationshipType.SELF
        ):
            return PermissionDecision(AccessLevel.FULL, None)

        grant = db.scalar(
            select(ConsentPermission)
            .where(
                ConsentPermission.profile_id == profile.id,
                ConsentPermission.grantee_user_id == requester_user_id,
            )
            .order_by(ConsentPermission.updated_at.desc(), ConsentPermission.id.desc())
        )
        if grant is not None:
            return PermissionDecision(grant.access_level, grant.id)
        return PermissionDecision(profile.access_level, None)

    @staticmethod
    def require_detail_access(decision: PermissionDecision) -> None:
        if not decision.may_view_details:
            raise ApiError(
                status_code=403,
                code="FAMILY_DETAIL_ACCESS_DENIED",
                message="Detailed family health records are not permitted for this profile.",
            )
