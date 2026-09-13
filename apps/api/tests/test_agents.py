"""Phase 13 routing, graph, safety, privacy, and trust-boundary tests."""

import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.router import route_intent
from app.agents.schemas import AgentIntent
from app.database.enums import ProvenanceType, VerificationStatus
from app.database.models import Observation, PendingHealthEntry, User
from tests.conftest import FakeLLMProvider
from tests.test_family import family_fixture


def create_profile(client: TestClient, user: User, name: str = "Agent profile") -> str:
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


@pytest.mark.parametrize(
    ("query", "intent"),
    [
        ("Sugar 165", AgentIntent.DAILY_LOG),
        ("What is my latest HbA1c?", AgentIntent.RECORD_LOOKUP),
        ("When was my thyroid condition first documented?", AgentIntent.TIMELINE_QUERY),
        ("Why do you say my HbA1c was 7.2%?", AgentIntent.EVIDENCE_QUERY),
        ("What changed with my post-meal glucose?", AgentIntent.ANALYTICS_QUERY),
        ("Which conditions repeat in my family?", AgentIntent.FAMILY_QUERY),
        ("Prepare my doctor visit summary.", AgentIntent.DOCTOR_VISIT),
        ("Should I double my metformin tonight?", AgentIntent.UNSUPPORTED_MEDICAL_ACTION),
        ("What does HbA1c mean?", AgentIntent.GENERAL_HEALTH_INFORMATION),
        ("Please help", AgentIntent.UNKNOWN),
    ],
)
def test_deterministic_router(query: str, intent: AgentIntent) -> None:
    assert route_intent(query) == intent


def test_urgent_and_medication_requests_short_circuit(client: TestClient, user: User) -> None:
    profile_id = create_profile(client, user)
    for message, decision in (
        ("Should I double my metformin tonight?", "BLOCK"),
        ("I have crushing chest pain and cannot breathe.", "ESCALATE"),
    ):
        response = client.post(
            f"/api/v1/profiles/{profile_id}/ask",
            json={"message": message, "include_trace": True},
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["safety"]["decision"] == decision
        assert payload["nodes_run"] == ["safety_pre"]
        assert payload["actions"] == ["safety_short_circuit"]
        assert "please" in payload["answer"].casefold()
        assert (
            "clinician" in payload["answer"].casefold()
            or "emergency" in payload["answer"].casefold()
        )


def test_ambiguous_daily_log_remains_pending(
    client: TestClient, db_session: Session, user: User, fake_llm: FakeLLMProvider
) -> None:
    profile_id = create_profile(client, user)
    fake_llm.response = json.dumps(
        {
            "observations": [
                {
                    "entry_type": "glucose",
                    "value": 165,
                    "unit": "mg/dL",
                    "context": "UNKNOWN",
                    "observed_at": None,
                    "confidence": 0.9,
                }
            ],
            "symptoms": [],
            "activities": [],
            "sleep_entries": [],
            "warnings": [],
        }
    )
    before = db_session.scalar(select(func.count()).select_from(Observation)) or 0

    response = client.post(
        f"/api/v1/profiles/{profile_id}/ask",
        json={"message": "Sugar 165", "include_trace": True},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["intent"] == "DAILY_LOG"
    assert payload["pending_id"]
    assert payload["clarification_required"] is True
    assert "daily_log" in payload["nodes_run"]
    assert (db_session.scalar(select(func.count()).select_from(Observation)) or 0) == before
    pending = db_session.get(PendingHealthEntry, payload["pending_id"])
    assert pending is not None
    assert pending.status.value == "NEEDS_CLARIFICATION"


def test_analytics_graph_uses_verified_sqlite_and_attaches_evidence(
    client: TestClient, db_session: Session, user: User
) -> None:
    profile_id = create_profile(client, user)
    rows = []
    for day, value in (
        ("2026-06-01", 140),
        ("2026-07-01", 145),
        ("2026-08-20", 170),
        ("2026-09-05", 175),
    ):
        rows.append(
            Observation(
                profile_id=profile_id,
                display_name="Glucose",
                value_number=value,
                unit="mg/dL",
                interpretation="AFTER_MEAL",
                observed_at=datetime.fromisoformat(day).replace(tzinfo=UTC),
                provenance=ProvenanceType.USER_REPORTED,
                verification_status=VerificationStatus.VERIFIED,
            )
        )
    rows.append(
        Observation(
            profile_id=profile_id,
            display_name="Glucose",
            value_number=999,
            unit="mg/dL",
            interpretation="AFTER_MEAL",
            observed_at=datetime(2026, 9, 10, tzinfo=UTC),
            provenance=ProvenanceType.AI_EXTRACTED,
            verification_status=VerificationStatus.PENDING,
        )
    )
    db_session.add_all(rows)
    db_session.commit()

    response = client.post(
        f"/api/v1/profiles/{profile_id}/ask",
        json={
            "message": "What changed with my post-meal glucose?",
            "include_trace": True,
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["intent"] == "ANALYTICS_QUERY"
    assert payload["nodes_run"] == [
        "safety_pre",
        "router",
        "analytics",
        "evidence",
        "explanation",
        "safety_post",
    ]
    assert payload["structured_result"]["recent_summary"]["mean"] == 172.5
    assert all(item["normalized_value"] != 999 for item in payload["evidence"])


def test_family_graph_never_exposes_private_profile_details(
    client: TestClient, db_session: Session, user: User
) -> None:
    profiles = family_fixture(db_session, user)
    response = client.post(
        f"/api/v1/profiles/{profiles['self'].id}/ask",
        json={"message": "Which conditions repeat in my family?", "include_trace": True},
    )

    assert response.status_code == 200, response.text
    serialized = json.dumps(response.json())
    assert response.json()["intent"] == "FAMILY_QUERY"
    assert "Secret sibling name" not in serialized
    assert "Hypertension" not in serialized
    assert "family_permission_check" in response.json()["actions"]


def test_post_safety_replaces_unsafe_model_output(
    client: TestClient, user: User, fake_llm: FakeLLMProvider
) -> None:
    profile_id = create_profile(client, user)
    fake_llm.response = json.dumps({"answer": "You should stop metformin."})

    response = client.post(
        f"/api/v1/profiles/{profile_id}/ask",
        json={"message": "Explain medication adherence generally", "include_trace": True},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["safety"]["decision"] == "BLOCK"
    assert payload["answer"] != "You should stop metformin."
    assert payload["nodes_run"][-1] == "safety_post"
