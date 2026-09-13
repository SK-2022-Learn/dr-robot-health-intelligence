"""Validate that live Doctor Visit generation mutates only append-only audit data."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen

from sqlalchemy import func, select

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPOSITORY_ROOT / "apps" / "api"
sys.path.insert(0, str(API_ROOT))

from app.database.models import AuditLog, HealthEvent, Medication, Observation, Symptom
from app.database.session import SessionLocal

PROFILE_ID = "18ad5348-36ba-574b-be47-84d8d2fd3419"
ENDPOINT = f"http://127.0.0.1:8000/api/v1/profiles/{PROFILE_ID}/doctor-visit/generate"


def rows(db: object, model: object) -> list[tuple[object, ...]]:
    records = db.scalars(select(model).where(model.profile_id == PROFILE_ID)).all()
    return sorted(
        tuple(
            str(getattr(record, field, None))
            for field in (
                "id",
                "title",
                "name",
                "display_name",
                "value_number",
                "value_text",
                "dose",
                "frequency",
                "is_active",
                "severity",
                "verification_status",
                "updated_at",
            )
        )
        for record in records
    )


def snapshot() -> tuple[dict[str, dict[str, object]], int]:
    with SessionLocal() as db:
        result = {}
        for model in (HealthEvent, Observation, Medication, Symptom):
            values = rows(db, model)
            result[model.__tablename__] = {
                "count": len(values),
                "sha256": hashlib.sha256(repr(values).encode()).hexdigest(),
            }
        audits = db.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(
                AuditLog.action == "DOCTOR_VISIT_BRIEF_GENERATED",
                AuditLog.after_state["profile_id"].as_string() == PROFILE_ID,
            )
        )
        return result, int(audits or 0)


before, audit_before = snapshot()
request = Request(ENDPOINT, method="POST")
with urlopen(request, timeout=30) as response:
    status = response.status
    body = json.load(response)
after, audit_after = snapshot()

print(
    json.dumps(
        {
            "http_status": status,
            "profile_id": body["profile_id"],
            "health_tables_unchanged": before == after,
            "before": before,
            "after": after,
            "audit_before": audit_before,
            "audit_after": audit_after,
            "audit_increment": audit_after - audit_before,
        },
        indent=2,
    )
)
