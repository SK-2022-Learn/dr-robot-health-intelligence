"""Seed an idempotent, entirely fictional Phase 12 Doctor Visit demo profile."""

from __future__ import annotations

import sys
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPOSITORY_ROOT / "apps" / "api"
sys.path.insert(0, str(API_ROOT))

from app.database.enums import (
    AccessLevel,
    DocumentStatus,
    HealthEventType,
    ProvenanceType,
    RelationshipType,
    VerificationStatus,
)
from app.database.models import (
    DocumentPage,
    EvidenceLink,
    HealthEvent,
    HealthProfile,
    Medication,
    Observation,
    SourceDocument,
    Symptom,
    User,
)
from app.database.session import SessionLocal

SEED_USERNAME = "demo-user"
PREFIX = "dr-robot-phase12-doctor-visit"
REFERENCE_DATE = date(2026, 9, 13)


def fixture_id(kind: str, label: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"{PREFIX}:{kind}:{label}"))


def timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def add_if_missing(db: object, row: object) -> bool:
    if db.get(type(row), row.id) is not None:
        return False
    db.add(row)
    return True


def seed_phase12_demo() -> dict[str, int]:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == SEED_USERNAME))
        if user is None:
            raise RuntimeError(
                "Run scripts/seed_demo.py before the Phase 12 fixture seed."
            )

        profile_id = fixture_id("profile", "doctor-visit-demo")
        empty_profile_id = fixture_id("profile", "doctor-visit-empty-demo")
        added = {
            "profiles": 0,
            "events": 0,
            "medications": 0,
            "observations": 0,
            "symptoms": 0,
            "evidence": 0,
        }
        for profile in (
            HealthProfile(
                id=profile_id,
                owner_user_id=user.id,
                display_name="Doctor Visit Demo",
                relationship_to_owner=RelationshipType.OTHER,
                date_of_birth=date(1968, 3, 22),
                sex="female",
                access_level=AccessLevel.PRIVATE,
                is_active=True,
            ),
            HealthProfile(
                id=empty_profile_id,
                owner_user_id=user.id,
                display_name="Doctor Visit Empty Demo",
                relationship_to_owner=RelationshipType.OTHER,
                date_of_birth=date(1975, 7, 10),
                access_level=AccessLevel.PRIVATE,
                is_active=True,
            ),
        ):
            added["profiles"] += int(add_if_missing(db, profile))
        db.flush()

        document_id = fixture_id("document", "trusted-record")
        add_if_missing(
            db,
            SourceDocument(
                id=document_id,
                profile_id=profile_id,
                original_filename="fictional-doctor-visit-record.pdf",
                stored_filename="phase12-fictional-doctor-visit-record.pdf",
                mime_type="application/pdf",
                storage_path="data/demo/fictional-doctor-visit-record.pdf",
                document_date=REFERENCE_DATE,
                status=DocumentStatus.PARSED,
                extracted_text=(
                    "Fictional demonstration record: diabetes, thyroid condition, past TB "
                    "treatment, metformin 500 mg twice daily, HbA1c 7.2%."
                ),
                page_count=1,
            ),
        )
        add_if_missing(
            db,
            DocumentPage(
                id=fixture_id("page", "trusted-record-1"),
                document_id=document_id,
                page_number=1,
                text=(
                    "FICTIONAL DEMO RECORD\nDiabetes documented. Thyroid condition "
                    "documented. Past TB treatment completed. Metformin 500 mg twice daily. "
                    "HbA1c 7.2%. Fasting glucose 118 mg/dL."
                ),
            ),
        )
        db.flush()

        event_specs = (
            ("diabetes", HealthEventType.CONDITION, date(2012, 4, 1), "Diabetes"),
            (
                "thyroid",
                HealthEventType.CONDITION,
                date(2016, 8, 1),
                "Thyroid condition",
            ),
            ("tb", HealthEventType.PROCEDURE, date(2001, 1, 1), "Past TB treatment"),
        )
        targets: list[tuple[str, str]] = []
        for key, event_type, event_date, title in event_specs:
            row_id = fixture_id("event", key)
            added["events"] += int(
                add_if_missing(
                    db,
                    HealthEvent(
                        id=row_id,
                        profile_id=profile_id,
                        event_type=event_type,
                        event_date=event_date,
                        title=title,
                        verification_status=VerificationStatus.VERIFIED,
                        provenance=ProvenanceType.DOCUMENT_VERIFIED,
                        source_document_id=document_id,
                        created_by_user_id=user.id,
                    ),
                )
            )
            targets.append(("health_event_id", row_id))

        medication_id = fixture_id("medication", "metformin")
        added["medications"] += int(
            add_if_missing(
                db,
                Medication(
                    id=medication_id,
                    profile_id=profile_id,
                    name="Metformin",
                    dose="500",
                    dose_unit="mg",
                    frequency="twice daily",
                    route="oral",
                    start_date=date(2022, 1, 1),
                    is_active=True,
                    provenance=ProvenanceType.DOCUMENT_VERIFIED,
                    verification_status=VerificationStatus.VERIFIED,
                ),
            )
        )
        targets.append(("medication_id", medication_id))

        observation_specs = [
            ("hba1c", "HbA1c", 7.2, "%", "2026-09-11", None),
            ("fasting", "Fasting glucose", 118, "mg/dL", "2026-09-12", "FASTING"),
            ("pressure", "Blood pressure", None, "mmHg", "2026-09-12", None),
            ("weight", "Weight", 70.3, "kg", "2026-09-10", None),
        ]
        baseline = zip(
            (145, 148, 151, 147, 149),
            ("2026-05-17", "2026-06-05", "2026-06-25", "2026-07-15", "2026-08-14"),
            strict=True,
        )
        recent = zip(
            (168, 172, 176, 171, 173),
            ("2026-08-15", "2026-08-22", "2026-08-29", "2026-09-05", "2026-09-13"),
            strict=True,
        )
        observation_specs.extend(
            (f"postmeal-{day}", "Glucose", value, "mg/dL", day, "AFTER_MEAL")
            for value, day in (*baseline, *recent)
        )
        for key, name, value, unit, observed_at, context in observation_specs:
            row_id = fixture_id("observation", key)
            added["observations"] += int(
                add_if_missing(
                    db,
                    Observation(
                        id=row_id,
                        profile_id=profile_id,
                        display_name=name,
                        value_number=float(value) if value is not None else None,
                        value_text="126/78" if key == "pressure" else None,
                        unit=unit,
                        interpretation=context,
                        observed_at=timestamp(observed_at),
                        provenance=ProvenanceType.DOCUMENT_VERIFIED,
                        verification_status=VerificationStatus.VERIFIED,
                    ),
                )
            )
            targets.append(("observation_id", row_id))

        for observed_at in ("2026-08-26", "2026-09-04", "2026-09-12"):
            row_id = fixture_id("symptom", f"constipation-{observed_at}")
            added["symptoms"] += int(
                add_if_missing(
                    db,
                    Symptom(
                        id=row_id,
                        profile_id=profile_id,
                        name="Constipation",
                        severity=3,
                        started_at=timestamp(observed_at),
                        notes="Fictional demo symptom report.",
                        provenance=ProvenanceType.USER_REPORTED,
                        verification_status=VerificationStatus.VERIFIED,
                    ),
                )
            )
            targets.append(("symptom_id", row_id))
        db.flush()

        for target_type, target_id in targets:
            link_id = fixture_id("evidence", f"{target_type}:{target_id}")
            added["evidence"] += int(
                add_if_missing(
                    db,
                    EvidenceLink(
                        id=link_id,
                        source_document_id=document_id,
                        page_number=1,
                        source_excerpt="Supporting fact in the fictional Phase 12 demo record.",
                        **{target_type: target_id},
                    ),
                )
            )
        db.commit()
        print(f"Phase 12 fictional Doctor Visit fixtures ready: {added}")
        print(f"Doctor Visit Demo profile id: {profile_id}")
        print(f"Doctor Visit Empty Demo profile id: {empty_profile_id}")
        return added


if __name__ == "__main__":
    seed_phase12_demo()
