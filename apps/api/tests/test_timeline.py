"""Phase 8 normalized timeline, evidence, gap, and isolation tests."""

import json
from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.enums import (
    CandidateStatus,
    HealthEventType,
    PendingHealthEntryStatus,
    ProvenanceType,
    VerificationStatus,
)
from app.database.models import (
    AuditLog,
    ExtractedCandidate,
    HealthEvent,
    Observation,
    PendingHealthEntry,
    User,
)
from tests.conftest import FakeLLMProvider


def create_profile(client: TestClient, user: User, name: str = "Timeline profile") -> str:
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


def upload_hba1c(client: TestClient, profile_id: str) -> str:
    response = client.post(
        f"/api/v1/profiles/{profile_id}/documents",
        files={"file": ("synthetic-hba1c.txt", b"HbA1c 7.2%", "text/plain")},
        data={"document_date": "2026-09-01"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def document_extraction() -> str:
    return json.dumps(
        {
            "document_date": "2026-09-01",
            "warnings": [],
            "conditions": [],
            "medications": [],
            "symptoms": [],
            "measurements": [],
            "labs": [
                {
                    "test_name": "HbA1c",
                    "value_number": 7.2,
                    "value_text": None,
                    "unit": "%",
                    "reference_low": None,
                    "reference_high": None,
                    "reference_range_text": None,
                    "collected_date": "2026-09-01",
                    "interpretation": None,
                    "confidence": 0.97,
                    "evidence_text": "HbA1c 7.2%",
                    "page_number": 1,
                }
            ],
        }
    )


def daily_glucose(value: float) -> str:
    return json.dumps(
        {
            "observations": [
                {
                    "entry_type": "glucose",
                    "value": value,
                    "unit": "mg/dL",
                    "context": "FASTING",
                    "observed_at": "2026-09-13T08:00:00Z",
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


def test_timeline_sorts_filters_and_uses_clinical_dates(
    client: TestClient, db_session: Session, user: User
) -> None:
    profile_id = create_profile(client, user)
    for year, event_type in (
        (2000, HealthEventType.CONDITION),
        (2007, HealthEventType.PROCEDURE),
        (2012, HealthEventType.CONDITION),
        (2024, HealthEventType.LAB),
        (2026, HealthEventType.CONDITION),
    ):
        db_session.add(
            HealthEvent(
                profile_id=profile_id,
                event_type=event_type,
                event_date=date(year, 1, 1),
                title=f"Event {year}",
                provenance=ProvenanceType.USER_REPORTED,
                verification_status=VerificationStatus.VERIFIED,
            )
        )
    db_session.commit()

    descending = client.get(f"/api/v1/profiles/{profile_id}/timeline")
    ascending = client.get(f"/api/v1/profiles/{profile_id}/timeline", params={"sort": "asc"})
    conditions = client.get(f"/api/v1/profiles/{profile_id}/timeline", params={"type": "CONDITION"})
    bounded = client.get(
        f"/api/v1/profiles/{profile_id}/timeline",
        params={"from": "2007-01-01", "to": "2024-12-31", "limit": 2, "offset": 1},
    )

    assert descending.status_code == ascending.status_code == conditions.status_code == 200
    assert [item["title"] for item in descending.json()["items"]] == [
        "Event 2026",
        "Event 2024",
        "Event 2012",
        "Event 2007",
        "Event 2000",
    ]
    assert [item["title"] for item in ascending.json()["items"]] == list(
        reversed([item["title"] for item in descending.json()["items"]])
    )
    assert {item["timeline_type"] for item in conditions.json()["items"]} == {"CONDITION"}
    assert bounded.json()["total"] == 3
    assert [item["title"] for item in bounded.json()["items"]] == [
        "Event 2012",
        "Event 2007",
    ]
    assert client.get("/api/v1/profiles/missing/timeline").status_code == 404


def test_document_timeline_evidence_includes_page_and_does_not_mutate_fact(
    client: TestClient,
    db_session: Session,
    user: User,
    fake_llm: FakeLLMProvider,
) -> None:
    profile_id = create_profile(client, user)
    document_id = upload_hba1c(client, profile_id)
    fake_llm.response = document_extraction()
    assert client.post(f"/api/v1/documents/{document_id}/extract").status_code == 200
    candidate = client.get(f"/api/v1/documents/{document_id}/candidates").json()[0]
    accepted = client.post(f"/api/v1/candidates/{candidate['id']}/accept").json()
    observation_id = accepted["trusted_record"]["record_id"]
    before_audits = db_session.scalar(select(func.count(AuditLog.id)))

    timeline = client.get(f"/api/v1/profiles/{profile_id}/timeline").json()
    item = next(row for row in timeline["items"] if row["entity_id"] == observation_id)
    evidence = client.get(f"/api/v1/profiles/{profile_id}/evidence/observation/{observation_id}")

    assert item["timeline_type"] == "LAB"
    assert item["description"] == "7.2 %"
    assert item["source_type"] == "DOCUMENT"
    assert item["has_evidence"] is True
    assert evidence.status_code == 200
    assert evidence.json()["source"] == {
        "type": "DOCUMENT",
        "document_id": document_id,
        "filename": "synthetic-hba1c.txt",
        "document_date": "2026-09-01",
        "page_number": 1,
        "excerpt": "HbA1c 7.2%",
        "page_text": "HbA1c 7.2%",
        "view_source_path": f"/uploads?document={document_id}&page=1",
    }
    gaps = client.get(f"/api/v1/profiles/{profile_id}/evidence/gaps").json()["gaps"]
    assert not any(gap["entity_id"] == observation_id for gap in gaps)
    assert db_session.get(Observation, observation_id).value_number == 7.2
    assert db_session.scalar(select(func.count(AuditLog.id))) == before_audits


def test_chat_evidence_and_correction_preserve_original_message(
    client: TestClient,
    db_session: Session,
    user: User,
    fake_llm: FakeLLMProvider,
) -> None:
    profile_id = create_profile(client, user)
    conversation_id = client.post(f"/api/v1/profiles/{profile_id}/conversations", json={}).json()[
        "id"
    ]
    fake_llm.response = daily_glucose(181)
    posted = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "Fasting glucose 181 mg/dL"},
    ).json()
    corrected = posted["extraction"]
    corrected["observations"][0]["value"] = 118
    assert (
        client.patch(
            f"/api/v1/chat/pending/{posted['pending_id']}",
            json={"extraction": corrected},
        ).status_code
        == 200
    )
    confirmation = client.post(f"/api/v1/chat/pending/{posted['pending_id']}/confirm").json()
    observation_id = confirmation["trusted_records"][0]["record_id"]

    timeline = client.get(f"/api/v1/profiles/{profile_id}/timeline").json()
    item = next(row for row in timeline["items"] if row["entity_id"] == observation_id)
    evidence = client.get(
        f"/api/v1/profiles/{profile_id}/evidence/observation/{observation_id}"
    ).json()

    assert item["description"] == "118 mg/dL"
    assert item["source_type"] == "CHAT"
    assert item["has_correction"] is True
    assert evidence["source"]["label"] == "USER-REPORTED SOURCE"
    assert evidence["source"]["message"] == "Fasting glucose 181 mg/dL"
    assert evidence["saved_value"] == "118 mg/dL"
    assert evidence["correction_history"][0]["original_value"] == "181 mg/dL"
    assert evidence["correction_history"][0]["corrected_value"] == "118 mg/dL"
    assert evidence["correction_history"][0]["changed_fields"] == ["observations.0.value"]


def test_pending_and_rejected_candidates_and_chat_never_enter_timeline(
    client: TestClient,
    db_session: Session,
    user: User,
    fake_llm: FakeLLMProvider,
) -> None:
    profile_id = create_profile(client, user)
    document_id = upload_hba1c(client, profile_id)
    fake_llm.response = document_extraction()
    client.post(f"/api/v1/documents/{document_id}/extract")
    candidate = db_session.scalar(select(ExtractedCandidate))
    assert candidate is not None and candidate.status == CandidateStatus.PENDING

    conversation_id = client.post(f"/api/v1/profiles/{profile_id}/conversations", json={}).json()[
        "id"
    ]
    fake_llm.response = daily_glucose(118)
    posted = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "Fasting glucose 118 mg/dL"},
    ).json()
    assert client.get(f"/api/v1/profiles/{profile_id}/timeline").json()["items"] == []

    client.post(f"/api/v1/candidates/{candidate.id}/reject")
    client.post(f"/api/v1/chat/pending/{posted['pending_id']}/reject")
    assert db_session.get(ExtractedCandidate, candidate.id).status == CandidateStatus.REJECTED
    assert (
        db_session.get(PendingHealthEntry, posted["pending_id"]).status
        == PendingHealthEntryStatus.REJECTED
    )
    assert client.get(f"/api/v1/profiles/{profile_id}/timeline").json()["items"] == []


def test_missing_evidence_is_structural_and_never_fabricated(
    client: TestClient, db_session: Session, user: User
) -> None:
    profile_id = create_profile(client, user)
    event = HealthEvent(
        profile_id=profile_id,
        event_type=HealthEventType.CONDITION,
        event_date=date(2024, 1, 1),
        title="Synthetic condition",
        provenance=ProvenanceType.USER_REPORTED,
        verification_status=VerificationStatus.VERIFIED,
    )
    db_session.add(event)
    db_session.commit()

    gaps = client.get(f"/api/v1/profiles/{profile_id}/evidence/gaps").json()["gaps"]
    evidence = client.get(f"/api/v1/profiles/{profile_id}/evidence/health_event/{event.id}").json()

    assert any(gap["type"] == "MISSING_SOURCE" and gap["entity_id"] == event.id for gap in gaps)
    assert evidence["source_type"] == "MANUAL"
    assert evidence["source"]["message"] == (
        "No linked source evidence is available for this record."
    )


def test_timeline_and_evidence_are_profile_isolated(
    client: TestClient, db_session: Session, user: User
) -> None:
    profile_a = create_profile(client, user, "Profile A")
    profile_b = create_profile(client, user, "Profile B")
    observation_a = Observation(
        profile_id=profile_a,
        display_name="Glucose",
        value_number=118,
        unit="mg/dL",
        observed_at=datetime(2026, 9, 13, tzinfo=UTC),
        provenance=ProvenanceType.USER_REPORTED,
        verification_status=VerificationStatus.VERIFIED,
    )
    observation_b = Observation(
        profile_id=profile_b,
        display_name="TSH",
        value_number=4.8,
        unit="mIU/L",
        observed_at=datetime(2026, 9, 13, tzinfo=UTC),
        provenance=ProvenanceType.USER_REPORTED,
        verification_status=VerificationStatus.VERIFIED,
    )
    db_session.add_all((observation_a, observation_b))
    db_session.commit()

    timeline_a = client.get(f"/api/v1/profiles/{profile_a}/timeline").json()["items"]
    assert [item["title"] for item in timeline_a] == ["Glucose"]
    assert (
        client.get(
            f"/api/v1/profiles/{profile_a}/evidence/observation/{observation_b.id}"
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/v1/profiles/{profile_b}/evidence/observation/{observation_a.id}"
        ).status_code
        == 404
    )
