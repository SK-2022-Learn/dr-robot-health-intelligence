"""Add idempotent fictional Phase 9 analytics fixtures to the local demo profile."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPOSITORY_ROOT / "apps" / "api"
sys.path.insert(0, str(API_ROOT))

from app.database.enums import ProvenanceType, VerificationStatus  # noqa: E402
from app.database.models import HealthProfile, Observation, Symptom, User  # noqa: E402
from app.database.session import SessionLocal  # noqa: E402

SEED_USERNAME = "demo-user"
PREFIX = "dr-robot-phase9-demo"


def fixture_id(kind: str, label: str, observed_at: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"{PREFIX}:{kind}:{label}:{observed_at}"))


def timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def seed_phase9_demo() -> tuple[int, int]:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == SEED_USERNAME))
        if user is None:
            raise RuntimeError("Run scripts/seed_demo.py before the Phase 9 fixture seed.")
        profile = db.scalar(
            select(HealthProfile).where(
                HealthProfile.owner_user_id == user.id,
                HealthProfile.relationship_to_owner == "SELF",
            )
        )
        if profile is None:
            raise RuntimeError("The fictional SELF demo profile was not found.")

        baseline_dates = ("2026-05-17", "2026-06-05", "2026-06-25", "2026-07-15", "2026-08-14")
        recent_dates = ("2026-08-15", "2026-08-22", "2026-08-29", "2026-09-05", "2026-09-13")
        series = [
            ("Glucose", (145, 148, 151, 147, 149), baseline_dates, "mg/dL", "AFTER_MEAL"),
            ("Glucose", (168, 172, 176, 171, 173), recent_dates, "mg/dL", "AFTER_MEAL"),
            ("Weight", (70.0, 70.2, 70.1, 70.3), baseline_dates[:4], "kg", None),
            ("Weight", (70.2, 70.4, 70.1, 70.3), recent_dates[:4], "kg", None),
            ("Sleep duration", (480, 450), ("2026-06-01", "2026-08-01"), "min", None),
            ("Sleep duration", (360, 390), ("2026-08-20", "2026-09-10"), "min", None),
            ("Activity: walking", (20, 25, 30, 35, 40), baseline_dates, "min", None),
        ]
        observations_added = 0
        for name, values, dates, unit, context in series:
            for value, observed_at in zip(values, dates, strict=True):
                row_id = fixture_id("observation", f"{name}:{context}:{value}", observed_at)
                if db.get(Observation, row_id) is not None:
                    continue
                db.add(
                    Observation(
                        id=row_id,
                        profile_id=profile.id,
                        display_name=name,
                        value_number=float(value),
                        unit=unit,
                        interpretation=context,
                        observed_at=timestamp(observed_at),
                        provenance=ProvenanceType.USER_REPORTED,
                        verification_status=VerificationStatus.VERIFIED,
                    )
                )
                observations_added += 1

        symptom_dates = (
            "2026-06-01",
            "2026-07-15",
            "2026-08-16",
            "2026-08-25",
            "2026-09-03",
            "2026-09-12",
        )
        symptoms_added = 0
        for observed_at in symptom_dates:
            row_id = fixture_id("symptom", "Constipation", observed_at)
            if db.get(Symptom, row_id) is not None:
                continue
            db.add(
                Symptom(
                    id=row_id,
                    profile_id=profile.id,
                    name="Constipation",
                    severity=3,
                    started_at=timestamp(observed_at),
                    provenance=ProvenanceType.USER_REPORTED,
                    verification_status=VerificationStatus.VERIFIED,
                )
            )
            symptoms_added += 1
        db.commit()
        print(
            f"Phase 9 fictional fixtures ready: {observations_added} observations added, "
            f"{symptoms_added} symptoms added."
        )
        return observations_added, symptoms_added


if __name__ == "__main__":
    seed_phase9_demo()
