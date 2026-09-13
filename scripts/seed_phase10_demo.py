"""Add idempotent fictional Phase 10 family permissions and condition patterns."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

from sqlalchemy import func, select

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPOSITORY_ROOT / "apps" / "api"
sys.path.insert(0, str(API_ROOT))

from app.database.enums import (  # noqa: E402
    AccessLevel,
    DocumentStatus,
    HealthEventType,
    ProvenanceType,
    RelationshipType,
    VerificationStatus,
)
from app.database.models import (  # noqa: E402
    ConsentPermission,
    FamilyRelationship,
    HealthEvent,
    HealthProfile,
    SourceDocument,
    User,
)
from app.database.session import SessionLocal  # noqa: E402


def _condition(db: object, profile: HealthProfile, document: SourceDocument) -> None:
    exists = db.scalar(
        select(HealthEvent).where(
            HealthEvent.profile_id == profile.id,
            HealthEvent.event_type == HealthEventType.CONDITION,
            func.lower(HealthEvent.title) == "diabetes",
        )
    )
    if exists is None:
        db.add(
            HealthEvent(
                profile_id=profile.id,
                event_type=HealthEventType.CONDITION,
                event_date=date(2020, 1, 1),
                title="Diabetes",
                description="Fictional Phase 10 demonstration record.",
                verification_status=VerificationStatus.VERIFIED,
                provenance=ProvenanceType.DOCUMENT_VERIFIED,
                source_document_id=document.id,
                created_by_user_id=profile.owner_user_id,
            )
        )


def _document(db: object, profile: HealthProfile) -> SourceDocument:
    stored = f"phase10-family-{profile.id}.txt"
    document = db.scalar(select(SourceDocument).where(SourceDocument.stored_filename == stored))
    if document is None:
        document = SourceDocument(
            profile_id=profile.id,
            original_filename=f"{profile.relationship_to_owner.value.lower()}-family-history.txt",
            stored_filename=stored,
            mime_type="text/plain",
            storage_path=f"data/demo/{stored}",
            document_date=date(2020, 1, 1),
            status=DocumentStatus.PARSED,
            extracted_text="Fictional record: Diabetes documented.",
            page_count=1,
        )
        db.add(document)
        db.flush()
    return document


def seed_phase10() -> dict[str, int]:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == "demo-user"))
        if user is None:
            raise RuntimeError("Run scripts/seed_demo.py before the Phase 10 seed.")
        profiles = {
            profile.display_name: profile
            for profile in db.scalars(
                select(HealthProfile).where(HealthProfile.owner_user_id == user.id)
            )
        }
        required = {"Lakshmi", "Grandparent A", "Grandparent B", "Parent A", "Parent B", "Sibling"}
        if not required.issubset(profiles):
            raise RuntimeError(
                "The fictional Phase 2 family is incomplete; reset and reseed first."
            )

        levels = {
            "Grandparent A": AccessLevel.FULL,
            "Grandparent B": AccessLevel.PRIVATE,
            "Parent A": AccessLevel.FAMILY_SUMMARY,
            "Parent B": AccessLevel.CAREGIVER,
            "Sibling": AccessLevel.PRIVATE,
        }
        for name, access in levels.items():
            profile = profiles[name]
            permission = db.scalar(
                select(ConsentPermission).where(
                    ConsentPermission.profile_id == profile.id,
                    ConsentPermission.grantee_user_id == user.id,
                )
            )
            if permission is None:
                profile.access_level = access
                db.add(
                    ConsentPermission(
                        profile_id=profile.id,
                        grantee_user_id=user.id,
                        access_level=access,
                        scope="family-health",
                    )
                )

        maternal_link = db.scalar(
            select(FamilyRelationship).where(
                FamilyRelationship.source_profile_id == profiles["Parent A"].id,
                FamilyRelationship.target_profile_id == profiles["Grandparent A"].id,
                FamilyRelationship.relationship_type == RelationshipType.GRANDMOTHER,
            )
        )
        if maternal_link is None:
            db.add(
                FamilyRelationship(
                    source_profile_id=profiles["Parent A"].id,
                    target_profile_id=profiles["Grandparent A"].id,
                    relationship_type=RelationshipType.GRANDMOTHER,
                )
            )

        for name in ("Lakshmi", "Parent A", "Grandparent A"):
            _condition(db, profiles[name], _document(db, profiles[name]))
        hidden = db.scalar(
            select(HealthEvent).where(
                HealthEvent.profile_id == profiles["Sibling"].id,
                HealthEvent.title == "Private sibling condition",
            )
        )
        if hidden is None:
            db.add(
                HealthEvent(
                    profile_id=profiles["Sibling"].id,
                    event_type=HealthEventType.CONDITION,
                    event_date=date(2021, 1, 1),
                    title="Private sibling condition",
                    verification_status=VerificationStatus.VERIFIED,
                    provenance=ProvenanceType.USER_REPORTED,
                    created_by_user_id=user.id,
                )
            )
        db.commit()
        result = {
            "profiles": int(db.scalar(select(func.count()).select_from(HealthProfile)) or 0),
            "relationships": int(
                db.scalar(select(func.count()).select_from(FamilyRelationship)) or 0
            ),
            "permissions": int(db.scalar(select(func.count()).select_from(ConsentPermission)) or 0),
            "conditions": int(
                db.scalar(
                    select(func.count())
                    .select_from(HealthEvent)
                    .where(HealthEvent.event_type == HealthEventType.CONDITION)
                )
                or 0
            ),
        }
        print(f"Fictional Phase 10 family seed ready: {result}")
        return result


if __name__ == "__main__":
    seed_phase10()
