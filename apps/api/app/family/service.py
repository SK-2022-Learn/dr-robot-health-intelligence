"""Family graph orchestration, consent updates, and safe audit events."""

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.database.enums import AccessLevel, HealthEventType, RelationshipType, VerificationStatus
from app.database.models import ConsentPermission, FamilyRelationship, HealthEvent, HealthProfile
from app.family.patterns import FamilyPatternService, normalize_condition
from app.family.permissions import PermissionService
from app.family.schemas import (
    FamilyGraphResponse,
    FamilyPatternsResponse,
    FamilyPermissionRead,
    FamilyProfileSummary,
)
from app.schemas.family import FamilyRelationshipRead
from app.services.audit import AuditService


class FamilyService:
    def __init__(
        self,
        permissions: PermissionService | None = None,
        patterns: FamilyPatternService | None = None,
        audit: AuditService | None = None,
    ) -> None:
        self.permissions = permissions or PermissionService()
        self.patterns = patterns or FamilyPatternService(self.permissions)
        self.audit = audit or AuditService()

    @staticmethod
    def _profiles(db: Session, owner_user_id: str) -> list[HealthProfile]:
        return list(
            db.scalars(
                select(HealthProfile)
                .where(
                    HealthProfile.owner_user_id == owner_user_id,
                    HealthProfile.is_active.is_(True),
                )
                .order_by(
                    HealthProfile.relationship_to_owner,
                    HealthProfile.display_name,
                    HealthProfile.id,
                )
            )
        )

    @staticmethod
    def _relationships(db: Session, profile_ids: list[str]) -> list[FamilyRelationship]:
        if not profile_ids:
            return []
        return list(
            db.scalars(
                select(FamilyRelationship)
                .where(
                    FamilyRelationship.source_profile_id.in_(profile_ids),
                    FamilyRelationship.target_profile_id.in_(profile_ids),
                )
                .order_by(FamilyRelationship.created_at, FamilyRelationship.id)
            )
        )

    @staticmethod
    def _labels(profiles: list[HealthProfile]) -> dict[str, str]:
        grouped: dict[RelationshipType, list[HealthProfile]] = defaultdict(list)
        for profile in profiles:
            grouped[profile.relationship_to_owner].append(profile)
        labels: dict[str, str] = {}
        base = {
            RelationshipType.SELF: "Self",
            RelationshipType.MOTHER: "Parent A",
            RelationshipType.FATHER: "Parent B",
            RelationshipType.SIBLING: "Sibling",
            RelationshipType.CHILD: "Child",
            RelationshipType.GRANDMOTHER: "Grandparent A",
            RelationshipType.GRANDFATHER: "Grandparent B",
            RelationshipType.OTHER: "Family member",
        }
        for relationship, rows in grouped.items():
            for index, profile in enumerate(rows):
                label = base[relationship]
                if len(rows) > 1:
                    label = f"{label} {index + 1}"
                labels[profile.id] = label
        return labels

    def _context(
        self, db: Session, selected_profile_id: str, requester_user_id: str
    ) -> tuple[list[HealthProfile], list[FamilyRelationship], dict[str, str]]:
        selected = self.permissions.require_family_anchor(
            db, selected_profile_id, requester_user_id
        )
        profiles = self._profiles(db, selected.owner_user_id)
        relationships = self._relationships(db, [profile.id for profile in profiles])
        return profiles, relationships, self._labels(profiles)

    def graph(
        self, db: Session, selected_profile_id: str, requester_user_id: str
    ) -> FamilyGraphResponse:
        profiles, relationships, labels = self._context(db, selected_profile_id, requester_user_id)
        permitted_ids = []
        decisions = {}
        for profile in profiles:
            decision = self.permissions.decision(db, profile, requester_user_id)
            decisions[profile.id] = decision
            if decision.may_view_summary:
                permitted_ids.append(profile.id)
        conditions = (
            list(
                db.scalars(
                    select(HealthEvent).where(
                        HealthEvent.profile_id.in_(permitted_ids),
                        HealthEvent.event_type == HealthEventType.CONDITION,
                        HealthEvent.verification_status != VerificationStatus.REJECTED,
                    )
                )
            )
            if permitted_ids
            else []
        )
        by_profile: dict[str, set[str]] = defaultdict(set)
        frequency: dict[str, int] = defaultdict(int)
        display_names: dict[str, str] = {}
        for event in conditions:
            normalized = normalize_condition(event.title)
            display_names.setdefault(normalized, event.title.strip())
            if normalized not in by_profile[event.profile_id]:
                by_profile[event.profile_id].add(normalized)
                frequency[normalized] += 1

        summaries = []
        for profile in profiles:
            decision = decisions[profile.id]
            shared = sorted(
                display_names[name] for name in by_profile[profile.id] if frequency[name] >= 2
            )
            summaries.append(
                FamilyProfileSummary(
                    profile_id=profile.id,
                    label=labels[profile.id],
                    relationship_to_owner=profile.relationship_to_owner,
                    access_level=decision.access_level,
                    is_private=not decision.may_view_summary,
                    permission_id=decision.permission_id,
                    documented_condition_count=(
                        len(by_profile[profile.id]) if decision.may_view_details else None
                    ),
                    shared_conditions=(shared if decision.may_view_summary else None),
                )
            )
        self.audit.append(
            db,
            action="FAMILY_PROFILE_VIEWED",
            entity_type="health_profile",
            entity_id=selected_profile_id,
            actor_user_id=requester_user_id,
        )
        db.commit()
        return FamilyGraphResponse(
            requester_user_id=requester_user_id,
            selected_profile_id=selected_profile_id,
            profiles=summaries,
            relationships=[FamilyRelationshipRead.model_validate(row) for row in relationships],
        )

    def pattern_results(
        self,
        db: Session,
        selected_profile_id: str,
        requester_user_id: str,
        *,
        condition: str | None = None,
        branch: str | None = None,
    ) -> FamilyPatternsResponse:
        profiles, relationships, labels = self._context(db, selected_profile_id, requester_user_id)
        patterns = self.patterns.build(
            db,
            profiles,
            relationships,
            requester_user_id,
            labels,
            condition=condition,
            branch=branch,
        )
        self.audit.append(
            db,
            action="FAMILY_PATTERN_VIEWED",
            entity_type="health_profile",
            entity_id=selected_profile_id,
            actor_user_id=requester_user_id,
        )
        db.commit()
        return FamilyPatternsResponse(
            requester_user_id=requester_user_id,
            selected_profile_id=selected_profile_id,
            patterns=patterns,
        )

    def update_permission(
        self,
        db: Session,
        permission_id: str,
        requester_user_id: str,
        access_level: AccessLevel,
    ) -> FamilyPermissionRead:
        permission = db.get(ConsentPermission, permission_id)
        if permission is None:
            raise ApiError(
                status_code=404,
                code="FAMILY_PERMISSION_NOT_FOUND",
                message="Family permission was not found.",
            )
        profile = db.get(HealthProfile, permission.profile_id)
        if profile is None or profile.owner_user_id != requester_user_id:
            raise ApiError(
                status_code=403,
                code="FAMILY_PERMISSION_CHANGE_DENIED",
                message="The requester cannot change this permission.",
            )
        previous = permission.access_level
        permission.access_level = access_level
        db.flush()
        self.audit.append(
            db,
            action="FAMILY_PERMISSION_CHANGED",
            entity_type="consent_permission",
            entity_id=permission.id,
            actor_user_id=requester_user_id,
            before_state={"access_level": previous.value},
            after_state={"access_level": access_level.value},
        )
        db.commit()
        db.refresh(permission)
        return FamilyPermissionRead(
            permission_id=permission.id,
            profile_id=permission.profile_id,
            access_level=permission.access_level,
            scope=permission.scope,
        )
