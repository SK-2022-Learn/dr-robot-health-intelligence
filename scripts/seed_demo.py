"""Seed deterministic-in-shape, entirely fictional Phase 2 demonstration data."""

from __future__ import annotations

import sys
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import func, select

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPOSITORY_ROOT / "apps" / "api"
sys.path.insert(0, str(API_ROOT))

from app.database.enums import (  # noqa: E402
    AccessLevel,
    HealthEventType,
    ProvenanceType,
    RelationshipType,
    DocumentStatus,
    VerificationStatus,
)
from app.database.models import (  # noqa: E402
    FamilyRelationship,
    HealthEvent,
    HealthProfile,
    Medication,
    Observation,
    SourceDocument,
    User,
)
from app.database.session import SessionLocal  # noqa: E402
from app.repositories.observation import ObservationRepository  # noqa: E402
from app.repositories.user import UserRepository  # noqa: E402
from app.schemas.health_event import HealthEventCreate  # noqa: E402
from app.schemas.observation import ObservationCreate  # noqa: E402
from app.schemas.profile import ProfileCreate  # noqa: E402
from app.schemas.user import UserCreate  # noqa: E402
from app.services.audit import AuditService  # noqa: E402
from app.services.health_event import HealthEventService  # noqa: E402
from app.services.profile import ProfileService  # noqa: E402

SEED_USERNAME = "demo-user"


def database_counts(db: object) -> dict[str, int]:
    """Return stable counts used to verify seed idempotency."""

    return {
        "users": db.scalar(select(func.count()).select_from(User)),
        "profiles": db.scalar(select(func.count()).select_from(HealthProfile)),
        "events": db.scalar(select(func.count()).select_from(HealthEvent)),
        "observations": db.scalar(select(func.count()).select_from(Observation)),
    }


def seed_demo() -> dict[str, int]:
    """Insert the fictional family once and return resulting core counts."""

    with SessionLocal() as db:
        users = UserRepository()
        existing_user = users.get_by_username(db, SEED_USERNAME)
        if existing_user is not None:
            counts = database_counts(db)
            print(f"Demo seed already present; no rows added: {counts}")
            return counts

        user = users.create(
            db,
            UserCreate(username=SEED_USERNAME, email="demo-user@example.invalid"),
        )
        db.commit()

        profiles = ProfileService()
        profile_specs = [
            ("Lakshmi", RelationshipType.SELF, date(1958, 3, 15), "female"),
            ("Grandparent A", RelationshipType.GRANDMOTHER, date(1918, 6, 1), "female"),
            ("Grandparent B", RelationshipType.GRANDFATHER, date(1916, 9, 1), "male"),
            ("Parent A", RelationshipType.MOTHER, date(1938, 4, 1), "female"),
            ("Parent B", RelationshipType.FATHER, date(1935, 8, 1), "male"),
            ("Sibling", RelationshipType.SIBLING, date(1961, 11, 1), None),
        ]
        created_profiles = {}
        for name, relationship, birth_date, sex in profile_specs:
            created_profiles[name] = profiles.create_profile(
                db,
                ProfileCreate(
                    owner_user_id=user.id,
                    display_name=name,
                    relationship_to_owner=relationship,
                    date_of_birth=birth_date,
                    sex=sex,
                    access_level=AccessLevel.PRIVATE,
                ),
            )

        lakshmi = created_profiles["Lakshmi"]
        relations = [
            ("Grandparent A", RelationshipType.GRANDMOTHER),
            ("Grandparent B", RelationshipType.GRANDFATHER),
            ("Parent A", RelationshipType.MOTHER),
            ("Parent B", RelationshipType.FATHER),
            ("Sibling", RelationshipType.SIBLING),
        ]
        db.add_all(
            FamilyRelationship(
                source_profile_id=lakshmi.id,
                target_profile_id=created_profiles[name].id,
                relationship_type=relationship,
            )
            for name, relationship in relations
        )

        source_document = SourceDocument(
            profile_id=lakshmi.id,
            original_filename="fictional-lab-2026.pdf",
            stored_filename="demo-fictional-lab-2026.pdf",
            mime_type="application/pdf",
            storage_path="data/demo/fictional-lab-2026.pdf",
            document_date=date(2026, 6, 1),
            status=DocumentStatus.PARSED,
        )
        db.add(source_document)
        db.commit()

        event_service = HealthEventService()
        event_specs = [
            (date(2000, 1, 1), HealthEventType.CONDITION, "Diabetes documented"),
            (date(2007, 1, 1), HealthEventType.CONDITION, "Thyroid condition documented"),
            (date(2012, 1, 1), HealthEventType.PROCEDURE, "Past TB treatment completed"),
            (date(2024, 1, 1), HealthEventType.MEDICATION, "Medication updated"),
        ]
        created_events = {}
        for event_date, event_type, title in event_specs:
            created_events[title] = event_service.create_event(
                db,
                lakshmi.id,
                HealthEventCreate(
                    event_type=event_type,
                    event_date=event_date,
                    title=title,
                    verification_status=VerificationStatus.VERIFIED,
                    provenance=ProvenanceType.USER_REPORTED,
                    created_by_user_id=user.id,
                ),
            )

        lab_event = event_service.create_event(
            db,
            lakshmi.id,
            HealthEventCreate(
                event_type=HealthEventType.LAB,
                event_date=date(2026, 6, 1),
                title="Latest lab available",
                verification_status=VerificationStatus.VERIFIED,
                provenance=ProvenanceType.DOCUMENT_VERIFIED,
                source_document_id=source_document.id,
                created_by_user_id=user.id,
            ),
        )
        medication = Medication(
            profile_id=lakshmi.id,
            name="Fictional glucose medication",
            frequency="Once daily",
            start_date=date(2024, 1, 1),
            is_active=True,
            provenance=ProvenanceType.USER_REPORTED,
            verification_status=VerificationStatus.VERIFIED,
            source_event_id=created_events["Medication updated"].id,
        )
        db.add(medication)

        observation = ObservationRepository().create(
            db,
            ObservationCreate(
                profile_id=lakshmi.id,
                health_event_id=lab_event.id,
                code="HBA1C",
                display_name="HbA1c",
                value_number=7.2,
                unit="%",
                observed_at=datetime(2026, 6, 1, 9, 0, tzinfo=UTC),
                provenance=ProvenanceType.DOCUMENT_VERIFIED,
                verification_status=VerificationStatus.VERIFIED,
            ),
        )
        AuditService().append(
            db,
            action="observation.created",
            entity_type="observation",
            entity_id=observation.id,
            actor_user_id=user.id,
            after_state={"display_name": "HbA1c", "value_number": 7.2, "unit": "%"},
        )
        db.commit()

        counts = database_counts(db)
        print(f"Fictional demo seed created: {counts}")
        return counts


if __name__ == "__main__":
    seed_demo()
