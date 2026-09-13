"""Phase 9 deterministic personal-baseline analytics and API tests."""

import json
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.analytics.numeric import normalize_observation
from app.analytics.schemas import AnalyticsMetric
from app.database.enums import ProvenanceType, VerificationStatus
from app.database.models import Observation, Symptom, User
from tests.conftest import FakeLLMProvider

REFERENCE_DATE = date(2026, 9, 13)
BASELINE_DATES = ("2026-05-17", "2026-06-05", "2026-06-25", "2026-07-15", "2026-08-14")
RECENT_DATES = ("2026-08-15", "2026-08-22", "2026-08-29", "2026-09-05", "2026-09-13")


def create_profile(client: TestClient, user: User, name: str = "Analytics profile") -> str:
    response = client.post(
        "/api/v1/profiles",
        json={
            "owner_user_id": user.id,
            "display_name": name,
            "relationship_to_owner": "SELF",
            "access_level": "PRIVATE",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def at(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def observation(
    profile_id: str,
    name: str,
    value: float | None,
    unit: str,
    observed_at: str,
    *,
    value_text: str | None = None,
    context: str | None = None,
    status: VerificationStatus = VerificationStatus.VERIFIED,
) -> Observation:
    return Observation(
        profile_id=profile_id,
        display_name=name,
        value_number=value,
        value_text=value_text,
        unit=unit,
        interpretation=context,
        observed_at=at(observed_at),
        provenance=ProvenanceType.USER_REPORTED,
        verification_status=status,
    )


def add_series(
    db: Session,
    profile_id: str,
    name: str,
    values: tuple[float, ...],
    dates: tuple[str, ...],
    unit: str,
    *,
    context: str | None = None,
) -> None:
    db.add_all(
        observation(profile_id, name, value, unit, observed_at, context=context)
        for value, observed_at in zip(values, dates, strict=True)
    )


def trend(
    client: TestClient,
    profile_id: str,
    metric: str,
    *,
    context: str | None = None,
    explain: bool = False,
) -> dict:
    params: dict[str, object] = {
        "metric": metric,
        "reference_date": REFERENCE_DATE.isoformat(),
        "include_explanation": explain,
    }
    if context:
        params["context"] = context
    response = client.get(f"/api/v1/profiles/{profile_id}/analytics/trends", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_numeric_increase_exact_windows_statistics_context_and_evidence(
    client: TestClient, db_session: Session, user: User
) -> None:
    profile_id = create_profile(client, user)
    add_series(
        db_session,
        profile_id,
        "Glucose",
        (145, 148, 151, 147, 149),
        BASELINE_DATES,
        "mg/dL",
        context="AFTER_MEAL",
    )
    add_series(
        db_session,
        profile_id,
        "Glucose",
        (168, 172, 176, 171, 173),
        RECENT_DATES,
        "mg/dL",
        context="AFTER_MEAL",
    )
    add_series(
        db_session,
        profile_id,
        "Glucose",
        (90, 91, 92, 93, 94),
        RECENT_DATES,
        "mg/dL",
        context="FASTING",
    )
    db_session.add(
        observation(
            profile_id,
            "Glucose",
            999,
            "mg/dL",
            "2026-09-13",
            context="AFTER_MEAL",
            status=VerificationStatus.PENDING,
        )
    )
    db_session.commit()

    result = trend(client, profile_id, "glucose", context="AFTER_MEAL")

    assert result["recent_period"] == {
        "start": "2026-08-15",
        "end": "2026-09-13",
        "days": 30,
        "boundaries": "inclusive",
    }
    assert result["baseline_period"]["start"] == "2026-05-17"
    assert result["baseline_period"]["end"] == "2026-08-14"
    assert result["recent_summary"]["mean"] == 172
    assert result["baseline_summary"]["mean"] == 148
    assert result["absolute_change"] == 24
    assert result["percent_change"] == pytest.approx(16.2162)
    assert result["classification"] == "INCREASED"
    assert result["confidence"] == "HIGH"
    assert result["calculation_version"] == "numeric-trend-v1"
    assert [row["normalized_value"] for row in result["evidence"][-5:]] == [
        168,
        172,
        176,
        171,
        173,
    ]
    assert all(row["verification_status"] == "VERIFIED" for row in result["evidence"])
    assert all("/evidence/observation/" in row["evidence_path"] for row in result["evidence"])


def test_stable_weight_normalization_and_moderate_confidence(
    client: TestClient, db_session: Session, user: User
) -> None:
    profile_id = create_profile(client, user)
    dates = BASELINE_DATES[:4]
    recent_dates = RECENT_DATES[:4]
    add_series(db_session, profile_id, "Weight", (70.0, 70.2, 70.1, 70.3), dates, "kg")
    add_series(db_session, profile_id, "Weight", (70.2, 70.4, 70.1, 70.3), recent_dates, "kg")
    pounds = observation(profile_id, "Weight", 154.324, "lb", "2026-09-13")
    db_session.commit()

    normalized = normalize_observation(pounds, AnalyticsMetric.WEIGHT)
    result = trend(client, profile_id, "weight")

    assert normalized is not None
    assert normalized.value == pytest.approx(70.0, abs=0.02)
    assert result["classification"] == "STABLE"
    assert result["absolute_change"] == pytest.approx(0.1)
    assert result["confidence"] == "MODERATE"
    assert result["unit"] == "kg"


def test_decreased_sleep_and_low_confidence(
    client: TestClient, db_session: Session, user: User
) -> None:
    profile_id = create_profile(client, user)
    add_series(
        db_session,
        profile_id,
        "Sleep duration",
        (480, 450),
        ("2026-06-01", "2026-08-01"),
        "min",
    )
    add_series(
        db_session,
        profile_id,
        "Sleep duration",
        (360, 390),
        ("2026-08-20", "2026-09-10"),
        "min",
    )
    db_session.commit()

    result = trend(client, profile_id, "sleep_duration")

    assert result["baseline_summary"]["mean"] == 465
    assert result["recent_summary"]["mean"] == 375
    assert result["absolute_change"] == -90
    assert result["classification"] == "DECREASED"
    assert result["confidence"] == "LOW"


def test_insufficient_activity_does_not_insert_missing_days_as_zero(
    client: TestClient, db_session: Session, user: User
) -> None:
    profile_id = create_profile(client, user)
    add_series(
        db_session,
        profile_id,
        "Activity: walking",
        (20, 25, 30, 35, 40),
        BASELINE_DATES,
        "min",
    )
    add_series(
        db_session,
        profile_id,
        "Activity: walking",
        (45,),
        ("2026-09-01",),
        "min",
    )
    db_session.commit()

    result = trend(client, profile_id, "activity_duration")

    assert result["classification"] == "INSUFFICIENT_DATA"
    assert result["confidence"] == "INSUFFICIENT"
    assert result["recent_count"] == 1
    assert result["recent_summary"]["mean"] == 45
    assert any("at least 2" in message for message in result["missing_data"])


def test_blood_pressure_components_are_analyzed_separately(
    client: TestClient, db_session: Session, user: User
) -> None:
    profile_id = create_profile(client, user)
    for value, observed_at in zip(("120/75", "122/76"), BASELINE_DATES[:2], strict=True):
        db_session.add(
            observation(
                profile_id,
                "Blood pressure",
                None,
                "mmHg",
                observed_at,
                value_text=value,
            )
        )
    for value, observed_at in zip(("130/74", "132/75"), RECENT_DATES[:2], strict=True):
        db_session.add(
            observation(
                profile_id,
                "Blood pressure",
                None,
                "mmHg",
                observed_at,
                value_text=value,
            )
        )
    db_session.commit()

    systolic = trend(client, profile_id, "systolic_blood_pressure")
    diastolic = trend(client, profile_id, "diastolic_blood_pressure")

    assert systolic["baseline_summary"]["mean"] == 121
    assert systolic["recent_summary"]["mean"] == 131
    assert systolic["classification"] == "INCREASED"
    assert diastolic["baseline_summary"]["mean"] == 75.5
    assert diastolic["recent_summary"]["mean"] == 74.5
    assert diastolic["classification"] == "STABLE"
    assert "hypertension" not in systolic["explanation"].lower()


def test_symptom_frequency_compares_rates_without_diagnosis(
    client: TestClient, db_session: Session, user: User
) -> None:
    profile_id = create_profile(client, user)
    for observed_at in ("2026-06-01", "2026-07-15"):
        db_session.add(
            Symptom(
                profile_id=profile_id,
                name="Constipation",
                severity=3,
                started_at=at(observed_at),
                provenance=ProvenanceType.USER_REPORTED,
                verification_status=VerificationStatus.VERIFIED,
            )
        )
    for observed_at in ("2026-08-16", "2026-08-25", "2026-09-03", "2026-09-12"):
        db_session.add(
            Symptom(
                profile_id=profile_id,
                name="Constipation",
                severity=3,
                started_at=at(observed_at),
                provenance=ProvenanceType.USER_REPORTED,
                verification_status=VerificationStatus.VERIFIED,
            )
        )
    db_session.commit()

    response = client.get(
        f"/api/v1/profiles/{profile_id}/analytics/symptoms/Constipation",
        params={"reference_date": REFERENCE_DATE.isoformat()},
    )
    result = response.json()

    assert response.status_code == 200
    assert result["baseline_count"] == 2
    assert result["recent_count"] == 4
    assert result["classification"] == "INCREASED"
    assert "more frequently" in result["explanation"]
    assert "because" not in result["explanation"].lower()


def test_missing_symptom_period_is_unknown_not_absent(
    client: TestClient, db_session: Session, user: User
) -> None:
    profile_id = create_profile(client, user)
    db_session.add(
        Symptom(
            profile_id=profile_id,
            name="Headache",
            started_at=at("2026-09-01"),
            provenance=ProvenanceType.USER_REPORTED,
            verification_status=VerificationStatus.VERIFIED,
        )
    )
    db_session.commit()

    result = client.get(
        f"/api/v1/profiles/{profile_id}/analytics/symptoms/Headache",
        params={"reference_date": REFERENCE_DATE.isoformat()},
    ).json()

    assert result["classification"] == "INSUFFICIENT_DATA"
    assert result["baseline_rate_per_day"] is None
    assert "absence was not assumed" in result["missing_data"][0]


def test_llm_receives_completed_calculation_and_cannot_override_it(
    client: TestClient,
    db_session: Session,
    user: User,
    fake_llm: FakeLLMProvider,
) -> None:
    profile_id = create_profile(client, user)
    add_series(db_session, profile_id, "HbA1c", (6.0, 6.2), BASELINE_DATES[:2], "%")
    add_series(db_session, profile_id, "HbA1c", (7.0, 7.2), RECENT_DATES[:2], "%")
    db_session.commit()
    fake_llm.response = json.dumps(
        {
            "explanation": "The recorded recent average increased compared with your history.",
            "classification": "INCREASED",
            "recent_mean": 7.1,
            "baseline_mean": 6.1,
        }
    )

    accepted = trend(client, profile_id, "hba1c", explain=True)
    assert accepted["explanation_source"] == "LLM"
    assert '"absolute_change": 1.0' in fake_llm.calls[-1][0]

    fake_llm.response = json.dumps(
        {
            "explanation": "Altered numbers.",
            "classification": "DECREASED",
            "recent_mean": 1,
            "baseline_mean": 99,
        }
    )
    protected = trend(client, profile_id, "hba1c", explain=True)
    assert protected["classification"] == "INCREASED"
    assert protected["recent_summary"]["mean"] == 7.1
    assert protected["explanation_source"] == "TEMPLATE"

    fake_llm.available = False
    fallback = trend(client, profile_id, "hba1c", explain=True)
    assert fallback["classification"] == "INCREASED"
    assert fallback["explanation_source"] == "TEMPLATE"


def test_available_metrics_what_changed_validation_and_profile_isolation(
    client: TestClient, db_session: Session, user: User
) -> None:
    profile_a = create_profile(client, user, "Profile A")
    profile_b = create_profile(client, user, "Profile B")
    add_series(
        db_session,
        profile_a,
        "Glucose",
        (100, 101),
        BASELINE_DATES[:2],
        "mg/dL",
        context="FASTING",
    )
    add_series(
        db_session,
        profile_a,
        "Glucose",
        (110, 112),
        RECENT_DATES[:2],
        "mg/dL",
        context="FASTING",
    )
    add_series(
        db_session,
        profile_b,
        "Glucose",
        (900, 901),
        RECENT_DATES[:2],
        "mg/dL",
        context="FASTING",
    )
    db_session.add(
        observation(
            profile_a,
            "Glucose",
            777,
            "mg/dL",
            "2026-09-13",
            context="FASTING",
            status=VerificationStatus.REJECTED,
        )
    )
    db_session.commit()

    metrics = client.get(f"/api/v1/profiles/{profile_a}/analytics/metrics")
    changed = client.post(
        f"/api/v1/profiles/{profile_a}/analytics/what-changed",
        json={"reference_date": REFERENCE_DATE.isoformat()},
    )
    result = trend(client, profile_a, "glucose", context="FASTING")

    assert metrics.status_code == 200
    assert metrics.json()["metrics"] == [
        {"metric": "glucose", "label": "Glucose", "contexts": ["FASTING"]}
    ]
    assert metrics.json()["symptoms"] == []
    assert changed.status_code == 200
    assert changed.json()["results"][0]["display_priority"] == 1
    assert max(row["normalized_value"] for row in result["evidence"]) < 200
    assert (
        client.get(
            f"/api/v1/profiles/{profile_a}/analytics/trends",
            params={"metric": "weight", "context": "FASTING"},
        ).status_code
        == 400
    )
    assert (
        client.get(
            f"/api/v1/profiles/{profile_a}/analytics/trends", params={"metric": "invalid"}
        ).status_code
        == 422
    )
    assert (
        client.get(
            "/api/v1/profiles/missing/analytics/trends", params={"metric": "weight"}
        ).status_code
        == 404
    )


def test_since_window_validation(client: TestClient, user: User) -> None:
    profile_id = create_profile(client, user)
    custom = client.get(
        f"/api/v1/profiles/{profile_id}/analytics/trends",
        params={
            "metric": "weight",
            "reference_date": "2026-09-13",
            "recent_days": 10,
            "baseline_days": 20,
        },
    )
    response = client.post(
        f"/api/v1/profiles/{profile_id}/analytics/what-changed",
        json={"since": "2025-01-01", "reference_date": "2026-09-13"},
    )
    assert custom.status_code == 200
    assert custom.json()["recent_period"] == {
        "start": "2026-09-04",
        "end": "2026-09-13",
        "days": 10,
        "boundaries": "inclusive",
    }
    assert custom.json()["baseline_period"]["start"] == "2026-08-15"
    assert custom.json()["baseline_period"]["end"] == "2026-09-03"
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_ANALYTICS_WINDOW"
