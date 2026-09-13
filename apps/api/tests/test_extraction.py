"""Phase 5 structured extraction and human-review trust-boundary tests."""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.enums import CandidateStatus, ProvenanceType, VerificationStatus
from app.database.models import (
    AuditLog,
    EvidenceLink,
    ExtractedCandidate,
    HealthEvent,
    Medication,
    Observation,
    Symptom,
    User,
)
from tests.conftest import FakeLLMProvider


def create_profile(client: TestClient, user: User) -> str:
    response = client.post(
        "/api/v1/profiles",
        json={
            "owner_user_id": user.id,
            "display_name": "Extraction profile",
            "relationship_to_owner": "SELF",
            "access_level": "PRIVATE",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def upload_text(client: TestClient, profile_id: str, *, name: str = "phase-five.txt") -> str:
    response = client.post(
        f"/api/v1/profiles/{profile_id}/documents",
        files={
            "file": (
                name,
                (
                    b"Date: 2026-09-01\nKnown condition: Type 2 diabetes\n"
                    b"Metformin 500 mg twice daily\nFasting glucose: 181 mg/dL\n"
                    b"Reported symptom: Mild constipation\nWeight: 70 kg"
                ),
                "text/plain",
            )
        },
        data={"document_date": "2026-09-01"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def extraction_payload() -> dict[str, object]:
    return {
        "document_date": "2026-09-01",
        "warnings": [],
        "conditions": [
            {
                "condition_name": "Type 2 diabetes",
                "status": "known",
                "onset_date": "2026-09-01",
                "resolved_date": None,
                "confidence": 0.94,
                "evidence_text": "Known condition: Type 2 diabetes",
                "page_number": None,
            }
        ],
        "medications": [
            {
                "name": "Metformin",
                "dose": "500",
                "dose_unit": "mg",
                "frequency": "twice daily",
                "route": None,
                "start_date": None,
                "end_date": None,
                "active_status": "active",
                "confidence": 0.91,
                "evidence_text": "Metformin 500 mg twice daily",
                "page_number": 1,
            }
        ],
        "labs": [
            {
                "test_name": "Fasting glucose",
                "value_number": 181,
                "value_text": None,
                "unit": "mg/dL",
                "reference_low": None,
                "reference_high": None,
                "reference_range_text": None,
                "collected_date": "2026-09-01",
                "interpretation": None,
                "confidence": 0.97,
                "evidence_text": "Fasting glucose: 181 mg/dL",
                "page_number": 1,
            }
        ],
        "symptoms": [
            {
                "name": "Constipation",
                "severity": "mild",
                "started_at": None,
                "ended_at": None,
                "notes": None,
                "confidence": 0.82,
                "evidence_text": "Reported symptom: Mild constipation",
                "page_number": 1,
            }
        ],
        "measurements": [
            {
                "measurement_name": "Weight",
                "value_number": 70,
                "value_text": None,
                "unit": "kg",
                "context": None,
                "observed_at": "2026-09-01T08:00:00Z",
                "confidence": 0.88,
                "evidence_text": "Weight: 70 kg",
                "page_number": 1,
            }
        ],
    }


def run_extraction(
    client: TestClient,
    user: User,
    fake_llm: FakeLLMProvider,
    payload: dict[str, object] | None = None,
) -> tuple[str, str, list[dict[str, object]]]:
    profile_id = create_profile(client, user)
    document_id = upload_text(client, profile_id)
    fake_llm.response = json.dumps(payload or extraction_payload())
    response = client.post(f"/api/v1/documents/{document_id}/extract")
    assert response.status_code == 200, response.text
    candidates = client.get(f"/api/v1/documents/{document_id}/candidates").json()
    return profile_id, document_id, candidates


def trusted_count(db: Session) -> int:
    models = (HealthEvent, Observation, Medication, Symptom)
    return sum(db.scalar(select(func.count(model.id))) or 0 for model in models)


def test_extracts_all_types_without_trusted_writes_and_is_idempotent(
    client: TestClient,
    db_session: Session,
    user: User,
    fake_llm: FakeLLMProvider,
) -> None:
    before = trusted_count(db_session)
    _, document_id, candidates = run_extraction(client, user, fake_llm)

    assert trusted_count(db_session) == before
    assert len(candidates) == 5
    assert {candidate["candidate_type"] for candidate in candidates} == {
        "condition",
        "medication",
        "lab",
        "symptom",
        "measurement",
    }
    assert all(candidate["status"] == "PENDING" for candidate in candidates)
    assert all(candidate["evidence_text"] for candidate in candidates)
    assert all(candidate["page_number"] == 1 for candidate in candidates)
    assert "[PAGE 1]" in fake_llm.calls[0][0]
    assert "Fasting glucose: 181 mg/dL" in fake_llm.calls[0][0]
    assert "properties" in fake_llm.calls[0][1]

    repeated = client.post(f"/api/v1/documents/{document_id}/extract")
    assert repeated.status_code == 200
    assert repeated.json()["reused_existing"] is True
    assert repeated.json()["candidate_count"] == 5
    assert len(fake_llm.calls) == 1

    pending = client.get(
        f"/api/v1/documents/{document_id}/candidates", params={"status": "PENDING"}
    )
    assert pending.status_code == 200
    assert len(pending.json()) == 5
    audits = db_session.scalars(select(AuditLog).where(AuditLog.entity_id == document_id)).all()
    assert {audit.action for audit in audits} >= {
        "DOCUMENT_EXTRACTION_STARTED",
        "DOCUMENT_EXTRACTION_COMPLETED",
    }
    assert all("Fasting glucose: 181 mg/dL" not in str(audit.after_state) for audit in audits)


def test_rejects_evidence_that_is_not_present_in_the_source(
    client: TestClient,
    db_session: Session,
    user: User,
    fake_llm: FakeLLMProvider,
) -> None:
    profile_id = create_profile(client, user)
    document_id = upload_text(client, profile_id)
    payload = extraction_payload()
    payload["conditions"] = [
        {**payload["conditions"][0], "evidence_text": "Invented diagnosis: hypertension"}  # type: ignore[index]
    ]
    fake_llm.response = json.dumps(payload)

    response = client.post(f"/api/v1/documents/{document_id}/extract")

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "STRUCTURED_EXTRACTION_FAILED"
    assert db_session.scalar(select(func.count(ExtractedCandidate.id))) == 0


@pytest.mark.parametrize(
    "response",
    [
        "not-json",
        json.dumps(
            {
                **extraction_payload(),
                "labs": [{**extraction_payload()["labs"][0], "confidence": 1.5}],  # type: ignore[index]
            }
        ),
        json.dumps(
            {
                **extraction_payload(),
                "labs": [
                    {
                        **extraction_payload()["labs"][0],  # type: ignore[index]
                        "value_number": None,
                        "value_text": None,
                    }
                ],
            }
        ),
        json.dumps(
            {
                **extraction_payload(),
                "conditions": [
                    {
                        key: value
                        for key, value in extraction_payload()["conditions"][0].items()  # type: ignore[index,union-attr]
                        if key != "evidence_text"
                    }
                ],
            }
        ),
    ],
)
def test_invalid_model_output_is_controlled_and_saves_no_candidates(
    client: TestClient,
    db_session: Session,
    user: User,
    fake_llm: FakeLLMProvider,
    response: str,
) -> None:
    profile_id = create_profile(client, user)
    document_id = upload_text(client, profile_id)
    fake_llm.response = response

    result = client.post(f"/api/v1/documents/{document_id}/extract")

    assert result.status_code == 502
    assert result.json()["error"]["code"] == "STRUCTURED_EXTRACTION_FAILED"
    assert db_session.scalar(select(func.count(ExtractedCandidate.id))) == 0
    actions = db_session.scalars(
        select(AuditLog.action).where(AuditLog.entity_id == document_id)
    ).all()
    assert "DOCUMENT_EXTRACTION_FAILED" in actions


def test_extraction_requires_existing_parsed_text(
    client: TestClient, user: User, fake_llm: FakeLLMProvider
) -> None:
    missing = client.post("/api/v1/documents/missing/extract")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "DOCUMENT_NOT_FOUND"

    profile_id = create_profile(client, user)
    image = client.post(
        f"/api/v1/profiles/{profile_id}/documents",
        files={"file": ("scan.png", synthetic_png(), "image/png")},
    )
    assert image.status_code == 201
    blocked = client.post(f"/api/v1/documents/{image.json()['id']}/extract")
    assert blocked.status_code == 422
    assert blocked.json()["error"]["code"] == "DOCUMENT_NOT_PARSED"
    assert fake_llm.calls == []


def synthetic_png() -> bytes:
    from io import BytesIO

    from PIL import Image

    output = BytesIO()
    Image.new("RGB", (8, 8), "white").save(output, format="PNG")
    return output.getvalue()


def test_accepts_every_candidate_type_with_human_verified_provenance(
    client: TestClient,
    db_session: Session,
    user: User,
    fake_llm: FakeLLMProvider,
) -> None:
    _, _, candidates = run_extraction(client, user, fake_llm)

    for candidate in candidates:
        response = client.post(f"/api/v1/candidates/{candidate['id']}/accept")
        assert response.status_code == 200, response.text
        assert response.json()["candidate"]["status"] == "ACCEPTED"
        assert response.json()["trusted_record"] is not None

    assert db_session.scalar(select(func.count(HealthEvent.id))) == 1
    assert db_session.scalar(select(func.count(Medication.id))) == 1
    assert db_session.scalar(select(func.count(Symptom.id))) == 1
    assert db_session.scalar(select(func.count(Observation.id))) == 2
    assert db_session.scalar(select(func.count(EvidenceLink.id))) == 5
    assert db_session.scalar(select(func.count(EvidenceLink.medication_id))) == 1
    assert db_session.scalar(select(func.count(EvidenceLink.symptom_id))) == 1
    trusted = [
        *db_session.scalars(select(HealthEvent)).all(),
        *db_session.scalars(select(Medication)).all(),
        *db_session.scalars(select(Symptom)).all(),
        *db_session.scalars(select(Observation)).all(),
    ]
    assert all(item.provenance == ProvenanceType.AI_EXTRACTED for item in trusted)
    assert all(item.verification_status == VerificationStatus.VERIFIED for item in trusted)
    assert (
        db_session.scalar(
            select(func.count(AuditLog.id)).where(AuditLog.action == "CANDIDATE_ACCEPTED")
        )
        == 5
    )


def test_correction_preserves_original_and_writes_corrected_observation(
    client: TestClient,
    db_session: Session,
    user: User,
    fake_llm: FakeLLMProvider,
) -> None:
    _, _, candidates = run_extraction(client, user, fake_llm)
    lab = next(candidate for candidate in candidates if candidate["candidate_type"] == "lab")

    response = client.patch(
        f"/api/v1/candidates/{lab['id']}/correct",
        json={"structured_data": {"value_number": 118}},
    )

    assert response.status_code == 200, response.text
    assert response.json()["candidate"]["status"] == "CORRECTED"
    persisted = db_session.get(ExtractedCandidate, lab["id"])
    assert persisted is not None
    assert persisted.structured_data["value_number"] == 181
    observation = db_session.scalar(select(Observation))
    assert observation is not None
    assert observation.value_number == 118
    assert observation.provenance == ProvenanceType.USER_CORRECTED
    audit = db_session.scalar(
        select(AuditLog).where(
            AuditLog.entity_id == lab["id"], AuditLog.action == "CANDIDATE_CORRECTED"
        )
    )
    assert audit is not None
    assert audit.before_state["structured_data"]["value_number"] == 181
    assert audit.after_state["corrected_data"]["value_number"] == 118


def test_rejection_retains_candidate_and_creates_no_trusted_record(
    client: TestClient,
    db_session: Session,
    user: User,
    fake_llm: FakeLLMProvider,
) -> None:
    before = trusted_count(db_session)
    _, _, candidates = run_extraction(client, user, fake_llm)
    symptom = next(
        candidate for candidate in candidates if candidate["candidate_type"] == "symptom"
    )

    response = client.post(f"/api/v1/candidates/{symptom['id']}/reject")

    assert response.status_code == 200
    assert response.json()["candidate"]["status"] == "REJECTED"
    assert response.json()["trusted_record"] is None
    assert trusted_count(db_session) == before
    persisted = db_session.get(ExtractedCandidate, symptom["id"])
    assert persisted is not None and persisted.status == CandidateStatus.REJECTED
    assert (
        db_session.scalar(
            select(func.count(AuditLog.id)).where(
                AuditLog.entity_id == symptom["id"], AuditLog.action == "CANDIDATE_REJECTED"
            )
        )
        == 1
    )


def test_failed_review_validation_leaves_candidate_pending(
    client: TestClient,
    db_session: Session,
    user: User,
    fake_llm: FakeLLMProvider,
) -> None:
    payload = extraction_payload()
    payload["medications"] = [
        {**payload["medications"][0], "active_status": "unknown"}  # type: ignore[index]
    ]
    payload["conditions"] = []
    payload["labs"] = []
    payload["symptoms"] = []
    payload["measurements"] = []
    _, _, candidates = run_extraction(client, user, fake_llm, payload)

    response = client.post(f"/api/v1/candidates/{candidates[0]['id']}/accept")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "CANDIDATE_REQUIRES_CORRECTION"
    persisted = db_session.get(ExtractedCandidate, candidates[0]["id"])
    assert persisted is not None and persisted.status == CandidateStatus.PENDING
    assert trusted_count(db_session) == 0
