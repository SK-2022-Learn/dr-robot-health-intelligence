"""Phase 7 daily chat, clarification, trust-boundary, and isolation tests."""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.chat.parser import supplement_explicit_facts
from app.chat.schemas import DailyHealthExtraction, GlucoseEntry
from app.chat.service import ChatService
from app.database.enums import PendingHealthEntryStatus, ProvenanceType
from app.database.models import (
    AuditLog,
    Conversation,
    HealthEvent,
    Message,
    Observation,
    PendingHealthEntry,
    Symptom,
    User,
)
from tests.conftest import FakeLLMProvider


def leaf_values(value: object) -> list[object]:
    if isinstance(value, dict):
        return [leaf for item in value.values() for leaf in leaf_values(item)]
    if isinstance(value, list):
        return [leaf for item in value for leaf in leaf_values(item)]
    return [value]


def create_profile(client: TestClient, user: User, name: str) -> str:
    response = client.post(
        "/api/v1/profiles",
        json={
            "owner_user_id": user.id,
            "display_name": name,
            "relationship_to_owner": "SELF",
            "access_level": "PRIVATE",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def create_conversation(client: TestClient, profile_id: str) -> str:
    response = client.post(f"/api/v1/profiles/{profile_id}/conversations", json={})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def extraction(
    *,
    observations: list[dict] | None = None,
    symptoms: list[dict] | None = None,
    activities: list[dict] | None = None,
    sleep_entries: list[dict] | None = None,
) -> str:
    return json.dumps(
        {
            "observations": observations or [],
            "symptoms": symptoms or [],
            "activities": activities or [],
            "sleep_entries": sleep_entries or [],
            "clarifications": [],
            "warnings": [],
        }
    )


def glucose(value: float, context: str) -> dict:
    return {
        "entry_type": "glucose",
        "value": value,
        "unit": "mg/dL",
        "context": context,
        "observed_at": None,
        "confidence": 0.97,
    }


def trusted_count(db: Session) -> int:
    return sum(
        db.scalar(select(func.count()).select_from(model)) or 0
        for model in (HealthEvent, Observation, Symptom)
    )


def test_explicit_fact_reconciliation_restores_supported_model_omissions() -> None:
    result = supplement_explicit_facts(
        DailyHealthExtraction(),
        (
            "Morning sugar 118 before food. After breakfast sugar 172. "
            "Slept 6 hours. Little constipation today. Walked 25 minutes. "
            "BP 128/78 this morning. Weight 72 kg."
        ),
    )

    glucose_entries = [item for item in result.observations if isinstance(item, GlucoseEntry)]
    assert [(item.value, item.context.value) for item in glucose_entries] == [
        (118, "FASTING"),
        (172, "AFTER_MEAL"),
    ]
    assert result.sleep_entries[0].duration_minutes == 360
    assert result.symptoms[0].name == "Constipation"
    assert result.symptoms[0].severity.value == "MILD"
    assert result.activities[0].duration_minutes == 25
    assert any(item.entry_type == "blood_pressure" for item in result.observations)
    assert any(item.entry_type == "weight" for item in result.observations)


def test_explicit_fact_reconciliation_removes_ungrounded_model_facts() -> None:
    model_result = DailyHealthExtraction.model_validate_json(
        extraction(
            observations=[glucose(999, "RANDOM")],
            symptoms=[
                {
                    "name": "Nausea",
                    "severity": "SEVERE",
                    "started_at": None,
                    "duration_text": None,
                    "notes": None,
                    "confidence": 0.9,
                }
            ],
            sleep_entries=[
                {
                    "duration_minutes": 420,
                    "sleep_date": None,
                    "quality": None,
                    "confidence": 0.9,
                }
            ],
        )
    )

    result = supplement_explicit_facts(model_result, "Morning sugar 118 before food.")

    assert len(result.observations) == 1
    assert isinstance(result.observations[0], GlucoseEntry)
    assert result.observations[0].value == 118
    assert result.sleep_entries == []
    assert result.symptoms == []


def test_basic_chat_persists_preview_without_trusted_records_then_confirms(
    client: TestClient,
    db_session: Session,
    user: User,
    fake_llm: FakeLLMProvider,
) -> None:
    profile_id = create_profile(client, user, "Profile A")
    conversation_id = create_conversation(client, profile_id)
    fake_llm.response = extraction(
        observations=[glucose(118, "FASTING")],
        sleep_entries=[
            {
                "duration_minutes": 360,
                "sleep_date": None,
                "quality": None,
                "confidence": 0.94,
            }
        ],
    )
    before = trusted_count(db_session)

    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "Morning sugar 118 before food. Slept 6 hours."},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "STRUCTURED_PREVIEW"
    assert body["extraction"]["observations"][0]["value"] == 118
    assert body["extraction"]["observations"][0]["context"] == "FASTING"
    assert body["extraction"]["sleep_entries"][0]["duration_minutes"] == 360
    assert trusted_count(db_session) == before
    pending = db_session.get(PendingHealthEntry, body["pending_id"])
    assert pending is not None
    assert pending.status == PendingHealthEntryStatus.PENDING_REVIEW
    assert "never diagnose" in fake_llm.calls[-1][0].lower()

    confirmed = client.post(f"/api/v1/chat/pending/{pending.id}/confirm")

    assert confirmed.status_code == 200, confirmed.text
    assert len(confirmed.json()["trusted_records"]) == 2
    assert trusted_count(db_session) == before + 2
    rows = list(
        db_session.scalars(
            select(Observation).where(Observation.source_message_id == body["message_id"])
        )
    )
    assert {row.display_name for row in rows} == {"Glucose", "Sleep duration"}
    assert all(row.provenance == ProvenanceType.USER_REPORTED for row in rows)


def test_glucose_and_weight_ambiguity_require_allowlisted_clarification(
    client: TestClient,
    db_session: Session,
    user: User,
    fake_llm: FakeLLMProvider,
) -> None:
    profile_id = create_profile(client, user, "Profile A")
    conversation_id = create_conversation(client, profile_id)
    fake_llm.response = extraction(observations=[glucose(165, "UNKNOWN")])

    glucose_response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "Sugar 165"},
    )

    assert glucose_response.status_code == 200
    body = glucose_response.json()
    assert body["status"] == "NEEDS_CLARIFICATION"
    assert body["questions"][0]["question"] == (
        "Was this reading fasting, before a meal, after a meal, or random?"
    )
    assert db_session.scalar(select(func.count()).select_from(Observation)) == 0
    invalid = client.post(
        f"/api/v1/chat/pending/{body['pending_id']}/clarify",
        json={"answers": {"profile_id": "another-profile"}},
    )
    assert invalid.status_code == 422
    clarified = client.post(
        f"/api/v1/chat/pending/{body['pending_id']}/clarify",
        json={"answers": {body["questions"][0]["field"]: "FASTING"}},
    )
    assert clarified.status_code == 200
    assert clarified.json()["status"] == "STRUCTURED_PREVIEW"
    assert clarified.json()["extraction"]["observations"][0]["context"] == "FASTING"

    fake_llm.response = extraction(
        observations=[
            {
                "entry_type": "weight",
                "value": 72,
                "unit": None,
                "observed_at": None,
                "confidence": 0.95,
            }
        ]
    )
    weight_response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "Weight 72"},
    )
    assert weight_response.json()["status"] == "NEEDS_CLARIFICATION"
    assert "kg or 72 lb" in weight_response.json()["questions"][0]["question"]
    assert db_session.scalar(select(func.count()).select_from(Observation)) == 0


def test_multi_fact_message_maps_all_supported_entries(
    client: TestClient,
    db_session: Session,
    user: User,
    fake_llm: FakeLLMProvider,
) -> None:
    profile_id = create_profile(client, user, "Profile A")
    conversation_id = create_conversation(client, profile_id)
    fake_llm.response = extraction(
        observations=[
            glucose(172, "AFTER_MEAL"),
            {
                "entry_type": "blood_pressure",
                "systolic": 128,
                "diastolic": 78,
                "unit": "mmHg",
                "observed_at": None,
                "confidence": 0.97,
            },
            {
                "entry_type": "weight",
                "value": 72,
                "unit": "kg",
                "observed_at": None,
                "confidence": 0.95,
            },
        ],
        symptoms=[
            {
                "name": "Constipation",
                "severity": "MILD",
                "started_at": None,
                "duration_text": None,
                "notes": None,
                "confidence": 0.91,
            }
        ],
        activities=[
            {
                "activity_type": "walking",
                "duration_minutes": 25,
                "distance": None,
                "distance_unit": None,
                "observed_at": None,
                "confidence": 0.96,
            }
        ],
    )
    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={
            "content": (
                "After breakfast sugar 172. Mild constipation. Walked 25 minutes. "
                "BP 128/78. Weight 72 kg."
            )
        },
    )
    body = response.json()
    assert response.status_code == 200
    assert len(body["extraction"]["observations"]) == 3
    assert len(body["extraction"]["symptoms"]) == 1
    assert len(body["extraction"]["activities"]) == 1

    assert client.post(f"/api/v1/chat/pending/{body['pending_id']}/confirm").status_code == 200
    assert db_session.scalar(select(func.count()).select_from(Observation)) == 4
    observations = list(db_session.scalars(select(Observation)))
    assert any(
        row.display_name == "Blood pressure" and row.value_text == "128/78" for row in observations
    )
    assert any(row.display_name == "Weight" and row.unit == "kg" for row in observations)
    symptom = db_session.scalar(select(Symptom))
    assert symptom is not None and symptom.severity == 3


def test_correction_preserves_message_and_double_confirm_is_idempotent(
    client: TestClient,
    db_session: Session,
    user: User,
    fake_llm: FakeLLMProvider,
) -> None:
    profile_id = create_profile(client, user, "Profile A")
    conversation_id = create_conversation(client, profile_id)
    fake_llm.response = extraction(observations=[glucose(181, "FASTING")])
    posted = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "Fasting sugar 181."},
    ).json()
    corrected_extraction = posted["extraction"]
    corrected_extraction["observations"][0]["value"] = 118

    corrected = client.patch(
        f"/api/v1/chat/pending/{posted['pending_id']}",
        json={"extraction": corrected_extraction},
    )
    assert corrected.status_code == 200, corrected.text
    first = client.post(f"/api/v1/chat/pending/{posted['pending_id']}/confirm")
    second = client.post(f"/api/v1/chat/pending/{posted['pending_id']}/confirm")

    assert first.status_code == second.status_code == 200
    assert first.json()["already_confirmed"] is False
    assert second.json()["already_confirmed"] is True
    observations = list(
        db_session.scalars(
            select(Observation).where(Observation.source_message_id == posted["message_id"])
        )
    )
    assert len(observations) == 1
    assert observations[0].value_number == 118
    assert observations[0].provenance == ProvenanceType.USER_CORRECTED
    message = db_session.get(Message, posted["message_id"])
    assert message is not None and message.content == "Fasting sugar 181."
    actions = list(db_session.scalars(select(AuditLog.action)))
    assert "CHAT_ENTRY_CORRECTED" in actions
    assert "CHAT_ENTRY_CONFIRMED" in actions
    correction_audit = db_session.scalar(
        select(AuditLog).where(AuditLog.action == "CHAT_ENTRY_CORRECTED")
    )
    assert correction_audit is not None
    assert correction_audit.after_state["changed_fields"] == ["observations.0.value"]
    audit_values = [
        value
        for row in db_session.scalars(select(AuditLog))
        for value in leaf_values(row.after_state)
    ]
    assert 181 not in audit_values
    assert "181" not in audit_values
    assert "Fasting sugar 181." not in audit_values


def test_confirmation_rolls_back_every_trusted_record_on_failure(
    client: TestClient,
    db_session: Session,
    user: User,
    fake_llm: FakeLLMProvider,
) -> None:
    profile_id = create_profile(client, user, "Profile A")
    conversation_id = create_conversation(client, profile_id)
    fake_llm.response = extraction(
        observations=[glucose(118, "FASTING")],
        sleep_entries=[
            {
                "duration_minutes": 360,
                "sleep_date": None,
                "quality": None,
                "confidence": 0.94,
            }
        ],
    )
    posted = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "Morning sugar 118 before food. Slept 6 hours."},
    ).json()
    before = trusted_count(db_session)
    service = ChatService(fake_llm)
    create_records = service._create_trusted_records

    def fail_after_flush(db, pending, parsed):
        create_records(db, pending, parsed)
        raise RuntimeError("simulated confirmation failure")

    service._create_trusted_records = fail_after_flush  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="simulated confirmation failure"):
        service.confirm(db_session, posted["pending_id"])

    db_session.expire_all()
    pending = db_session.get(PendingHealthEntry, posted["pending_id"])
    assert pending is not None
    assert pending.status == PendingHealthEntryStatus.PENDING_REVIEW
    assert trusted_count(db_session) == before
    assert "CHAT_ENTRY_CONFIRMED" not in list(db_session.scalars(select(AuditLog.action)))


def test_reject_retains_pending_without_health_memory(
    client: TestClient,
    db_session: Session,
    user: User,
    fake_llm: FakeLLMProvider,
) -> None:
    profile_id = create_profile(client, user, "Profile A")
    conversation_id = create_conversation(client, profile_id)
    fake_llm.response = extraction(
        sleep_entries=[
            {
                "duration_minutes": 420,
                "sleep_date": None,
                "quality": None,
                "confidence": 0.9,
            }
        ]
    )
    posted = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "Slept 7 hours."},
    ).json()
    before = trusted_count(db_session)

    rejected = client.post(f"/api/v1/chat/pending/{posted['pending_id']}/reject")

    assert rejected.status_code == 200
    assert rejected.json()["status"] == "REJECTED"
    assert trusted_count(db_session) == before
    assert db_session.get(PendingHealthEntry, posted["pending_id"]) is not None


def test_profile_isolation_and_conversation_history(
    client: TestClient,
    db_session: Session,
    user: User,
    fake_llm: FakeLLMProvider,
) -> None:
    profile_a = create_profile(client, user, "Profile A")
    profile_b = create_profile(client, user, "Profile B")
    conversation_a = create_conversation(client, profile_a)
    create_conversation(client, profile_b)
    fake_llm.response = extraction(observations=[glucose(118, "FASTING")])
    posted = client.post(
        f"/api/v1/conversations/{conversation_a}/messages",
        json={"content": "Morning sugar 118 before food."},
    ).json()
    client.post(f"/api/v1/chat/pending/{posted['pending_id']}/confirm")

    assert (
        db_session.scalar(
            select(func.count()).select_from(Observation).where(Observation.profile_id == profile_a)
        )
        == 1
    )
    assert (
        db_session.scalar(
            select(func.count()).select_from(Observation).where(Observation.profile_id == profile_b)
        )
        == 0
    )
    detail = client.get(f"/api/v1/conversations/{conversation_a}")
    assert detail.status_code == 200
    assert [item["role"] for item in detail.json()["messages"]] == ["USER", "ASSISTANT"]
    assert detail.json()["messages"][0]["content"] == "Morning sugar 118 before food."
    assert len(client.get(f"/api/v1/profiles/{profile_a}/conversations").json()) == 1


def test_medication_question_returns_boundary_without_pending_entry(
    client: TestClient,
    db_session: Session,
    user: User,
    fake_llm: FakeLLMProvider,
) -> None:
    profile_id = create_profile(client, user, "Profile A")
    conversation_id = create_conversation(client, profile_id)
    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "Should I stop metformin?"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "SAFETY_BOUNDARY"
    assert "does not make medication-change decisions" in response.json()["assistant_message"]
    assert db_session.scalar(select(func.count()).select_from(PendingHealthEntry)) == 0
    assert fake_llm.calls == []
    assert db_session.scalar(select(func.count()).select_from(Conversation)) == 1
