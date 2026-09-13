"""Phase 11 deterministic safety policy, integration, audit, and isolation tests."""

import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.enums import ProvenanceType, VerificationStatus
from app.database.models import AuditLog, Observation, PendingHealthEntry, User
from app.safety.enums import SafetyCategory, SafetyDecision
from app.safety.policy import POLICY_VERSION
from app.safety.schemas import SafetyInput
from app.safety.service import SafetyService
from tests.conftest import FakeLLMProvider


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
    assert response.status_code == 201
    return response.json()["id"]


def create_conversation(client: TestClient, profile_id: str) -> str:
    response = client.post(f"/api/v1/profiles/{profile_id}/conversations", json={})
    assert response.status_code == 201
    return response.json()["id"]


@pytest.mark.parametrize(
    ("text", "decision", "category", "rule_prefix"),
    [
        (
            "I have crushing chest pain and cannot breathe.",
            SafetyDecision.ESCALATE,
            SafetyCategory.URGENT_SYMPTOM,
            "SAFE-URGENT-",
        ),
        (
            "My face is drooping and I cannot move my arm.",
            SafetyDecision.ESCALATE,
            SafetyCategory.URGENT_SYMPTOM,
            "SAFE-URGENT-",
        ),
        (
            "I am bleeding heavily and it will not stop.",
            SafetyDecision.ESCALATE,
            SafetyCategory.URGENT_SYMPTOM,
            "SAFE-URGENT-",
        ),
        (
            "I lost consciousness and just woke up.",
            SafetyDecision.ESCALATE,
            SafetyCategory.URGENT_SYMPTOM,
            "SAFE-URGENT-",
        ),
        (
            "Should I stop my metformin?",
            SafetyDecision.BLOCK,
            SafetyCategory.MEDICATION_CHANGE,
            "SAFE-MED-",
        ),
        (
            "Can I double my dose tonight?",
            SafetyDecision.BLOCK,
            SafetyCategory.MEDICATION_CHANGE,
            "SAFE-MED-",
        ),
        (
            "Do I have diabetes?",
            SafetyDecision.WARN,
            SafetyCategory.DIAGNOSIS_REQUEST,
            "SAFE-DIAG-",
        ),
        (
            "What medicine should I take?",
            SafetyDecision.BLOCK,
            SafetyCategory.PRESCRIBING_REQUEST,
            "SAFE-RX-",
        ),
        (
            "This herb cures diabetes.",
            SafetyDecision.BLOCK,
            SafetyCategory.UNSUPPORTED_CURE_CLAIM,
            "SAFE-CURE-",
        ),
        (
            "Can I stop my thyroid medicine and use a natural remedy?",
            SafetyDecision.BLOCK,
            SafetyCategory.TREATMENT_REPLACEMENT,
            "SAFE-TREAT-",
        ),
        (
            "Should I drink bleach as a treatment?",
            SafetyDecision.BLOCK,
            SafetyCategory.HIGH_RISK_SELF_TREATMENT,
            "SAFE-SELF-",
        ),
    ],
)
def test_pre_check_rule_categories(
    text: str,
    decision: SafetyDecision,
    category: SafetyCategory,
    rule_prefix: str,
) -> None:
    result = SafetyService().pre_check(SafetyInput(user_text=text))

    assert result.decision == decision
    assert result.category == category
    assert result.rule_id.startswith(rule_prefix)
    assert result.policy_version == POLICY_VERSION
    assert result.safe_response_override


@pytest.mark.parametrize(
    ("text", "category", "rule_id"),
    [
        ("What does HbA1c measure?", SafetyCategory.GENERAL_HEALTH_INFORMATION, "SAFE-GEN-001"),
        ("Fasting glucose 118 mg/dL", SafetyCategory.LOGGING_ONLY, "SAFE-LOG-001"),
        (
            "My doctor told me to stop metformin last year.",
            SafetyCategory.LOGGING_ONLY,
            "SAFE-HISTORY-001",
        ),
        (
            "I had chest pain in 2010 and it resolved.",
            SafetyCategory.LOGGING_ONLY,
            "SAFE-HISTORY-001",
        ),
    ],
)
def test_safe_and_historical_inputs_are_not_false_positives(
    text: str, category: SafetyCategory, rule_id: str
) -> None:
    result = SafetyService().pre_check(SafetyInput(user_text=text))

    assert result.decision == SafetyDecision.ALLOW
    assert result.category == category
    assert result.rule_id == rule_id
    assert result.emergency_guidance is False


@pytest.mark.parametrize(
    ("draft", "category", "rule_id"),
    [
        ("You should stop metformin.", SafetyCategory.MEDICATION_CHANGE, "SAFE-MED-POST-001"),
        (
            "Turmeric cures diabetes.",
            SafetyCategory.UNSUPPORTED_CURE_CLAIM,
            "SAFE-CURE-POST-001",
        ),
        ("You definitely have diabetes.", SafetyCategory.DIAGNOSIS_REQUEST, "SAFE-DIAG-POST-001"),
        (
            "I recommend you take 500 mg of this medicine.",
            SafetyCategory.PRESCRIBING_REQUEST,
            "SAFE-RX-POST-001",
        ),
        (
            "You can replace your prescribed medication with a natural remedy.",
            SafetyCategory.TREATMENT_REPLACEMENT,
            "SAFE-TREAT-POST-001",
        ),
    ],
)
def test_post_check_replaces_unsafe_drafts(
    draft: str, category: SafetyCategory, rule_id: str
) -> None:
    result = SafetyService().post_check(SafetyInput(user_text="Tell me more", draft_response=draft))

    assert result.decision == SafetyDecision.BLOCK
    assert result.category == category
    assert result.rule_id == rule_id
    assert result.safe_response_override
    assert draft not in result.safe_response_override


def test_post_check_allows_safe_information() -> None:
    result = SafetyService().post_check(
        SafetyInput(
            user_text="What does HbA1c measure?",
            draft_response=(
                "HbA1c reflects average blood glucose over the prior two to three months."
            ),
        )
    )
    assert result.decision == SafetyDecision.ALLOW
    assert result.rule_id == "SAFE-POST-ALLOW-001"


def test_safety_api_audits_metadata_without_sensitive_text(
    client: TestClient, db_session: Session, user: User
) -> None:
    profile_id = create_profile(client, user, "Profile A")
    secret_text = "Should I stop my metformin?"
    response = client.post(
        "/api/v1/safety/evaluate",
        json={
            "user_text": secret_text,
            "profile_id": profile_id,
            "context_type": "GENERAL_ASK",
            "source": "TEST",
        },
    )

    assert response.status_code == 200
    assert response.json()["decision"] == "BLOCK"
    audit = db_session.scalar(select(AuditLog).where(AuditLog.action == "SAFETY_BLOCK"))
    assert audit is not None
    assert audit.after_state == {
        "decision": "BLOCK",
        "category": "MEDICATION_CHANGE",
        "rule_id": "SAFE-MED-001",
        "policy_version": "safety-v1",
        "evaluation_stage": "PRE",
        "profile_id": profile_id,
    }
    assert secret_text not in str(audit.after_state)


def test_chat_precheck_short_circuits_and_audits_urgent_and_medication(
    client: TestClient,
    db_session: Session,
    user: User,
    fake_llm: FakeLLMProvider,
) -> None:
    profile_id = create_profile(client, user, "Profile A")
    conversation_id = create_conversation(client, profile_id)

    urgent = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "I have severe chest pain and I can't breathe."},
    )
    medication = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "Should I stop metformin?"},
    )

    assert urgent.json()["safety"]["decision"] == "ESCALATE"
    assert urgent.json()["status"] == "SAFETY_BOUNDARY"
    assert "diagnos" in urgent.json()["assistant_message"].casefold()
    assert medication.json()["safety"]["decision"] == "BLOCK"
    assert db_session.query(PendingHealthEntry).count() == 0
    assert fake_llm.calls == []
    actions = list(db_session.scalars(select(AuditLog.action)))
    assert "SAFETY_ESCALATION" in actions
    assert "SAFETY_BLOCK" in actions


def test_safe_information_and_logging_continue_through_chat(
    client: TestClient,
    user: User,
    fake_llm: FakeLLMProvider,
) -> None:
    profile_id = create_profile(client, user, "Profile A")
    conversation_id = create_conversation(client, profile_id)

    informational = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "What does HbA1c measure?"},
    )
    assert informational.json()["status"] == "INFORMATIONAL"
    assert informational.json()["safety"]["decision"] == "ALLOW"
    assert "two to three months" in informational.json()["assistant_message"]

    fake_llm.response = json.dumps(
        {
            "observations": [
                {
                    "entry_type": "glucose",
                    "value": 118,
                    "unit": "mg/dL",
                    "context": "FASTING",
                    "observed_at": None,
                    "confidence": 0.98,
                }
            ],
            "symptoms": [],
            "activities": [],
            "sleep_entries": [],
            "clarifications": [],
            "warnings": [],
        }
    )
    logged = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "Fasting glucose 118 mg/dL"},
    )
    assert logged.json()["status"] == "STRUCTURED_PREVIEW"
    assert logged.json()["extraction"]["observations"][0]["value"] == 118


def test_record_question_is_profile_isolated(
    client: TestClient, db_session: Session, user: User
) -> None:
    profile_a = create_profile(client, user, "Profile A")
    profile_b = create_profile(client, user, "Profile B")
    db_session.add_all(
        [
            Observation(
                profile_id=profile_a,
                display_name="HbA1c",
                value_number=6.1,
                observed_at=datetime(2026, 1, 1, tzinfo=UTC),
                provenance=ProvenanceType.USER_REPORTED,
                verification_status=VerificationStatus.VERIFIED,
            ),
            Observation(
                profile_id=profile_b,
                display_name="HbA1c",
                value_number=9.9,
                observed_at=datetime(2026, 2, 1, tzinfo=UTC),
                provenance=ProvenanceType.USER_REPORTED,
                verification_status=VerificationStatus.VERIFIED,
            ),
        ]
    )
    db_session.commit()
    conversation_id = create_conversation(client, profile_a)

    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "What was my latest HbA1c?"},
    )

    assert response.status_code == 200
    assert "6.1" in response.json()["assistant_message"]
    assert "9.9" not in response.json()["assistant_message"]
