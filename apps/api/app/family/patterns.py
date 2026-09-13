"""Deterministic repeated-condition aggregation over permitted profiles."""

import re
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.enums import (
    AccessLevel,
    HealthEventType,
    RelationshipType,
    VerificationStatus,
)
from app.database.models import FamilyRelationship, HealthEvent, HealthProfile
from app.family.evidence import FamilyEvidenceService
from app.family.permissions import PermissionDecision, PermissionService
from app.family.schemas import (
    FamilyConditionContributor,
    FamilyConditionPattern,
    FamilyDataConfidence,
    FamilyRecordState,
)

GENERATION = {
    RelationshipType.GRANDMOTHER: -2,
    RelationshipType.GRANDFATHER: -2,
    RelationshipType.MOTHER: -1,
    RelationshipType.FATHER: -1,
    RelationshipType.SELF: 0,
    RelationshipType.SIBLING: 0,
    RelationshipType.CHILD: 1,
    RelationshipType.OTHER: 0,
}


def normalize_condition(value: str) -> str:
    """Apply only case/space normalization; no clinical synonym inference."""

    return re.sub(r"\s+", " ", value.strip()).casefold()


@dataclass(frozen=True)
class ProfileContext:
    profile: HealthProfile
    label: str
    decision: PermissionDecision
    generation: int
    branch: str


class FamilyPatternService:
    def __init__(
        self,
        permissions: PermissionService | None = None,
        evidence: FamilyEvidenceService | None = None,
    ) -> None:
        self.permissions = permissions or PermissionService()
        self.evidence = evidence or FamilyEvidenceService()

    @staticmethod
    def _branch(
        profile: HealthProfile,
        relationships: list[FamilyRelationship],
        profiles: dict[str, HealthProfile],
    ) -> str:
        direct = profile.relationship_to_owner
        if direct is RelationshipType.MOTHER:
            return "maternal"
        if direct is RelationshipType.FATHER:
            return "paternal"
        if direct in {
            RelationshipType.SELF,
            RelationshipType.SIBLING,
            RelationshipType.CHILD,
        }:
            return "self/children"
        if direct in {RelationshipType.GRANDMOTHER, RelationshipType.GRANDFATHER}:
            for relation in relationships:
                if relation.target_profile_id != profile.id:
                    continue
                parent = profiles.get(relation.source_profile_id)
                if parent and parent.relationship_to_owner is RelationshipType.MOTHER:
                    return "maternal"
                if parent and parent.relationship_to_owner is RelationshipType.FATHER:
                    return "paternal"
        return "unknown"

    @staticmethod
    def _state(
        context: ProfileContext,
        matching: list[HealthEvent],
        all_conditions: list[HealthEvent],
    ) -> FamilyRecordState:
        if not context.decision.may_view_summary:
            return FamilyRecordState.PRIVATE
        if matching:
            return FamilyRecordState.DOCUMENTED
        if context.decision.access_level is AccessLevel.FAMILY_SUMMARY:
            return FamilyRecordState.UNKNOWN
        return FamilyRecordState.NOT_DOCUMENTED if all_conditions else FamilyRecordState.UNKNOWN

    @staticmethod
    def _confidence(
        contributors: list[FamilyConditionContributor],
        evidence_count: int,
    ) -> FamilyDataConfidence:
        verified = sum(
            row.verification_status is VerificationStatus.VERIFIED for row in contributors
        )
        if (
            len(contributors) >= 3
            and verified == len(contributors)
            and evidence_count >= len(contributors)
        ):
            return FamilyDataConfidence.HIGH
        if verified >= max(1, len(contributors) // 2) or evidence_count >= len(contributors) // 2:
            return FamilyDataConfidence.MODERATE
        return FamilyDataConfidence.LOW

    def build(
        self,
        db: Session,
        profiles: list[HealthProfile],
        relationships: list[FamilyRelationship],
        requester_user_id: str,
        labels: dict[str, str],
        *,
        condition: str | None = None,
        branch: str | None = None,
    ) -> list[FamilyConditionPattern]:
        profile_map = {profile.id: profile for profile in profiles}
        contexts = [
            ProfileContext(
                profile=profile,
                label=labels[profile.id],
                decision=self.permissions.decision(db, profile, requester_user_id),
                generation=GENERATION[profile.relationship_to_owner],
                branch=self._branch(profile, relationships, profile_map),
            )
            for profile in profiles
        ]
        permitted_ids = [row.profile.id for row in contexts if row.decision.may_view_summary]
        events = (
            list(
                db.scalars(
                    select(HealthEvent)
                    .where(
                        HealthEvent.profile_id.in_(permitted_ids),
                        HealthEvent.event_type == HealthEventType.CONDITION,
                        HealthEvent.verification_status != VerificationStatus.REJECTED,
                    )
                    .order_by(HealthEvent.event_date, HealthEvent.id)
                )
            )
            if permitted_ids
            else []
        )
        by_profile: dict[str, list[HealthEvent]] = defaultdict(list)
        by_condition: dict[str, dict[str, list[HealthEvent]]] = defaultdict(
            lambda: defaultdict(list)
        )
        display_names: dict[str, str] = {}
        for event in events:
            normalized = normalize_condition(event.title)
            if not normalized:
                continue
            by_profile[event.profile_id].append(event)
            by_condition[normalized][event.profile_id].append(event)
            display_names.setdefault(normalized, re.sub(r"\s+", " ", event.title.strip()))

        condition_filter = normalize_condition(condition) if condition else None
        results: list[FamilyConditionPattern] = []
        permitted_count = len(permitted_ids)
        for normalized in sorted(by_condition):
            if condition_filter and normalized != condition_filter:
                continue
            matching_profiles = by_condition[normalized]
            if len(matching_profiles) < 2:
                continue
            contributors: list[FamilyConditionContributor] = []
            evidence_count = 0
            states: list[FamilyConditionContributor] = []
            for context in contexts:
                matched = matching_profiles.get(context.profile.id, [])
                state = self._state(context, matched, by_profile.get(context.profile.id, []))
                event = matched[0] if matched else None
                refs = []
                source_count = 0
                if event is not None:
                    source_count, refs = self.evidence.for_condition_event(
                        db, event, include_details=context.decision.may_view_details
                    )
                    evidence_count += source_count
                row = FamilyConditionContributor(
                    profile_id=context.profile.id,
                    label=context.label,
                    access_level=context.decision.access_level,
                    state=state,
                    generation=context.generation,
                    branch=context.branch,
                    health_event_id=(
                        event.id if event and context.decision.may_view_details else None
                    ),
                    verification_status=(
                        event.verification_status
                        if event and context.decision.may_view_details
                        else None
                    ),
                    evidence=refs,
                )
                states.append(row)
                if state is FamilyRecordState.DOCUMENTED:
                    contributors.append(row)

            branches = sorted({row.branch for row in contributors})
            if branch and branch.casefold() not in {item.casefold() for item in branches}:
                continue
            generation_count = len({row.generation for row in contributors})
            confidence = self._confidence(contributors, evidence_count)
            notes = [
                "Counts include documented conditions from permitted profiles only.",
                "No record is represented as unknown or not documented, never as absence.",
            ]
            if any(row.state is FamilyRecordState.PRIVATE for row in states):
                notes.append(
                    "Private profiles are excluded from all condition counts and evidence."
                )
            name = display_names[normalized]
            results.append(
                FamilyConditionPattern(
                    condition_name=name,
                    profile_count=len(contributors),
                    permitted_profile_count=permitted_count,
                    generation_count=generation_count,
                    branches=branches,
                    contributing_profiles=contributors,
                    profile_states=states,
                    evidence_count=evidence_count,
                    confidence=confidence,
                    statement=(
                        f"{name} is documented in {len(contributors)} permitted family profiles "
                        f"across {generation_count} generation"
                        f"{'s' if generation_count != 1 else ''}."
                    ),
                    notes=notes,
                )
            )
        return results
