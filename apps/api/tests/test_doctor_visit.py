"""Phase 12 trusted Doctor Visit brief behavior and safety tests."""

import json
import re
from datetime import UTC, date, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.enums import (
    CandidateStatus,
    DocumentStatus,
    HealthEventType,
    MessageRole,
    PendingHealthEntryStatus,
    ProvenanceType,
    VerificationStatus,
)
from app.database.models import (
    AuditLog,
    Conversation,
    DocumentPage,
    EvidenceLink,
    ExtractedCandidate,
    HealthEvent,
    Medication,
    Message,
    Observation,
    PendingHealthEntry,
    SourceDocument,
    Symptom,
    User,
)
from app.doctor_visit.service import DoctorVisitService
from tests.conftest import FakeLLMProvider


def create_profile(client: TestClient, user: User, name: str = "Visit profile") -> str:
    response = client.post(
        "/api/v1/profiles",
        json={
            "owner_user_id": user.id,
            "display_name": name,
            "relationship_to_owner": "SELF",
            "date_of_birth": "1980-01-20",
            "access_level": "PRIVATE",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def moment(day: date) -> datetime:
    return datetime.combine(day, datetime.min.time(), tzinfo=UTC)


def add_observation(
    db: Session,
    profile_id: str,
    name: str,
    value: float,
    unit: str,
    day: date,
    *,
    context: str | None = None,
    status: VerificationStatus = VerificationStatus.VERIFIED,
) -> Observation:
    row = Observation(
        profile_id=profile_id,
        display_name=name,
        value_number=value,
        unit=unit,
        interpretation=context,
        observed_at=moment(day),
        provenance=ProvenanceType.USER_REPORTED,
        verification_status=status,
    )
    db.add(row)
    return row


def seed_complete_brief(
    db: Session,
    profile_id: str,
    *,
    reference: date,
) -> dict[str, object]:
    document = SourceDocument(
        profile_id=profile_id,
        original_filename="visit-source.pdf",
        stored_filename=f"{profile_id}-visit-source.pdf",
        mime_type="application/pdf",
        storage_path=f"tests/{profile_id}.pdf",
        document_date=reference - timedelta(days=2),
        status=DocumentStatus.PARSED,
        extracted_text="Diabetes. Thyroid condition. Metformin. HbA1c 7.2.",
        page_count=1,
    )
    db.add(document)
    db.flush()
    db.add(DocumentPage(document_id=document.id, page_number=1, text=document.extracted_text))

    events = [
        HealthEvent(
            profile_id=profile_id,
            event_type=HealthEventType.CONDITION,
            event_date=date(2018, 2, 1),
            title="Diabetes",
            verification_status=VerificationStatus.VERIFIED,
            provenance=ProvenanceType.DOCUMENT_VERIFIED,
            source_document_id=document.id,
        ),
        HealthEvent(
            profile_id=profile_id,
            event_type=HealthEventType.CONDITION,
            event_date=date(2015, 4, 1),
            title="Thyroid condition",
            verification_status=VerificationStatus.VERIFIED,
            provenance=ProvenanceType.DOCUMENT_VERIFIED,
            source_document_id=document.id,
        ),
        HealthEvent(
            profile_id=profile_id,
            event_type=HealthEventType.PROCEDURE,
            event_date=date(2005, 1, 1),
            title="Past TB treatment",
            verification_status=VerificationStatus.VERIFIED,
            provenance=ProvenanceType.DOCUMENT_VERIFIED,
            source_document_id=document.id,
        ),
        HealthEvent(
            profile_id=profile_id,
            event_type=HealthEventType.CONDITION,
            event_date=date(2020, 1, 1),
            title="PENDING-SECRET-CONDITION",
            verification_status=VerificationStatus.PENDING,
            provenance=ProvenanceType.AI_EXTRACTED,
        ),
        HealthEvent(
            profile_id=profile_id,
            event_type=HealthEventType.CONDITION,
            event_date=date(2020, 1, 1),
            title="REJECTED-SECRET-CONDITION",
            verification_status=VerificationStatus.REJECTED,
            provenance=ProvenanceType.AI_EXTRACTED,
        ),
    ]
    db.add_all(events)
    medication = Medication(
        profile_id=profile_id,
        name="Metformin",
        dose="500",
        dose_unit="mg",
        frequency="twice daily",
        start_date=date(2022, 1, 1),
        is_active=True,
        provenance=ProvenanceType.DOCUMENT_VERIFIED,
        verification_status=VerificationStatus.VERIFIED,
    )
    inactive = Medication(
        profile_id=profile_id,
        name="INACTIVE-SECRET-MEDICATION",
        is_active=False,
        provenance=ProvenanceType.DOCUMENT_VERIFIED,
        verification_status=VerificationStatus.VERIFIED,
    )
    db.add_all([medication, inactive])

    hba1c = add_observation(db, profile_id, "HbA1c", 7.2, "%", reference - timedelta(days=2))
    fasting = add_observation(
        db,
        profile_id,
        "Fasting glucose",
        118,
        "mg/dL",
        reference - timedelta(days=1),
        context="FASTING",
    )
    pressure = add_observation(
        db, profile_id, "Blood pressure", 126, "mmHg", reference - timedelta(days=1)
    )
    baseline_values = (145, 148, 151, 147, 149)
    recent_values = (168, 172, 176, 171, 173)
    baseline_days = (119, 100, 80, 60, 30)
    recent_days = (29, 21, 14, 7, 0)
    trend_rows = [
        add_observation(
            db,
            profile_id,
            "Glucose",
            value,
            "mg/dL",
            reference - timedelta(days=days),
            context="AFTER_MEAL",
        )
        for value, days in zip(
            baseline_values + recent_values,
            baseline_days + recent_days,
            strict=True,
        )
    ]
    add_observation(
        db,
        profile_id,
        "Glucose",
        999,
        "mg/dL",
        reference,
        context="AFTER_MEAL",
        status=VerificationStatus.PENDING,
    )
    symptoms = [
        Symptom(
            profile_id=profile_id,
            name="Constipation",
            severity=3,
            started_at=moment(reference - timedelta(days=days)),
            provenance=ProvenanceType.USER_REPORTED,
            verification_status=VerificationStatus.VERIFIED,
        )
        for days in (18, 9, 1)
    ]
    db.add_all(symptoms)
    db.flush()
    linked = [*events[:3], medication, hba1c, fasting, pressure, *trend_rows, *symptoms]
    for row in linked:
        source_name = getattr(row, "title", getattr(row, "name", "reading"))
        target = {
            HealthEvent: {"health_event_id": row.id},
            Medication: {"medication_id": row.id},
            Observation: {"observation_id": row.id},
            Symptom: {"symptom_id": row.id},
        }[type(row)]
        db.add(
            EvidenceLink(
                source_document_id=document.id,
                page_number=1,
                source_excerpt=f"Evidence for {source_name}",
                **target,
            )
        )
    db.commit()
    return {"document": document, "hba1c": hba1c, "profile_id": profile_id}


def test_brief_uses_only_verified_facts_and_reuses_analytics(
    client: TestClient, db_session: Session, user: User
) -> None:
    reference = date.today()
    profile_id = create_profile(client, user)
    seed_complete_brief(db_session, profile_id, reference=reference)

    response = client.post(f"/api/v1/profiles/{profile_id}/doctor-visit/generate")
    assert response.status_code == 200, response.text
    brief = response.json()
    serialized = json.dumps(brief)

    assert [row["title"] for row in brief["known_history"]] == [
        "Past TB treatment",
        "Thyroid condition",
        "Diabetes",
    ]
    assert "PENDING-SECRET-CONDITION" not in serialized
    assert "REJECTED-SECRET-CONDITION" not in serialized
    assert [row["name"] for row in brief["medications"]] == ["Metformin"]
    assert "INACTIVE-SECRET-MEDICATION" not in serialized
    assert brief["medications"][0]["reconciliation_needed"] is True
    assert {row["name"] for row in brief["recent_labs"]} >= {"HbA1c", "Fasting glucose"}
    assert brief["recent_symptoms"][0]["report_count"] == 3
    included_values = [row["value"] for row in brief["recent_labs"] + brief["recent_measurements"]]
    included_values.extend(
        str(point["normalized_value"])
        for change in brief["recent_changes"]
        for point in change["analysis"]["evidence"]
    )
    assert "999" not in included_values
    assert "999.0" not in included_values

    changed = next(
        row
        for row in brief["recent_changes"]
        if row["analysis"]["metric"] == "glucose" and row["analysis"]["context"] == "AFTER_MEAL"
    )
    direct = client.get(
        f"/api/v1/profiles/{profile_id}/analytics/trends",
        params={
            "metric": "glucose",
            "context": "AFTER_MEAL",
            "reference_date": reference.isoformat(),
        },
    ).json()
    assert changed["analysis"]["recent_summary"] == direct["recent_summary"]
    assert changed["analysis"]["baseline_summary"] == direct["baseline_summary"]
    assert changed["analysis"]["recent_summary"]["mean"] == 172
    assert changed["analysis"]["baseline_summary"]["mean"] == 148
    assert changed["analysis"]["calculation_version"] == "numeric-trend-v1"
    assert any(row["type"] == "MISSING_RECENT_THYROID_LAB" for row in brief["missing_evidence"])
    assert "Would updated thyroid testing be useful to discuss?" in {
        row["question"] for row in brief["questions_to_discuss"]
    }
    assert all(
        row["evidence"]["verification_status"] == "VERIFIED" for row in brief["known_history"]
    )


def test_brief_evidence_resolves_to_the_linked_document(
    client: TestClient, db_session: Session, user: User
) -> None:
    profile_id = create_profile(client, user)
    seeded = seed_complete_brief(db_session, profile_id, reference=date.today())
    brief = client.post(f"/api/v1/profiles/{profile_id}/doctor-visit/generate").json()
    lab = next(row for row in brief["recent_labs"] if row["name"] == "HbA1c")

    assert lab["evidence"]["source_label"] == "visit-source.pdf, page 1"
    evidence = client.get(lab["evidence"]["evidence_path"])
    assert evidence.status_code == 200
    assert evidence.json()["source"]["document_id"] == seeded["document"].id
    assert evidence.json()["source"]["page_number"] == 1


def test_untrusted_candidate_and_pending_chat_never_enter_brief(
    client: TestClient, db_session: Session, user: User
) -> None:
    profile_id = create_profile(client, user)
    document = SourceDocument(
        profile_id=profile_id,
        original_filename="pending.pdf",
        stored_filename=f"{profile_id}-pending.pdf",
        mime_type="application/pdf",
        storage_path="tests/pending.pdf",
        status=DocumentStatus.PARSED,
        page_count=1,
    )
    db_session.add(document)
    db_session.flush()
    db_session.add_all(
        [
            ExtractedCandidate(
                document_id=document.id,
                candidate_type="condition",
                raw_text="CANDIDATE-ONLY-SECRET",
                structured_data={"condition_name": "CANDIDATE-ONLY-SECRET"},
                confidence=0.99,
                status=CandidateStatus.PENDING,
            ),
            ExtractedCandidate(
                document_id=document.id,
                candidate_type="condition",
                raw_text="REJECTED-CANDIDATE-ONLY-SECRET",
                structured_data={"condition_name": "REJECTED-CANDIDATE-ONLY-SECRET"},
                confidence=0.99,
                status=CandidateStatus.REJECTED,
            ),
        ]
    )
    conversation = Conversation(profile_id=profile_id, title="Pending")
    db_session.add(conversation)
    db_session.flush()
    message = Message(
        conversation_id=conversation.id,
        role=MessageRole.USER,
        content="CHAT-PENDING-ONLY-SECRET",
    )
    rejected_message = Message(
        conversation_id=conversation.id,
        role=MessageRole.USER,
        content="CHAT-REJECTED-ONLY-SECRET",
    )
    db_session.add_all([message, rejected_message])
    db_session.flush()
    pending_structured = {
        "observations": [],
        "symptoms": [],
        "activities": [],
        "sleep_entries": [],
        "clarifications": [],
        "warnings": ["CHAT-PENDING-ONLY-SECRET"],
    }
    rejected_structured = {
        **pending_structured,
        "warnings": ["CHAT-REJECTED-ONLY-SECRET"],
    }
    db_session.add_all(
        [
            PendingHealthEntry(
                conversation_id=conversation.id,
                message_id=message.id,
                profile_id=profile_id,
                structured_data=pending_structured,
                original_structured_data=pending_structured,
                status=PendingHealthEntryStatus.PENDING_REVIEW,
                was_corrected=False,
            ),
            PendingHealthEntry(
                conversation_id=conversation.id,
                message_id=rejected_message.id,
                profile_id=profile_id,
                structured_data=rejected_structured,
                original_structured_data=rejected_structured,
                status=PendingHealthEntryStatus.REJECTED,
                was_corrected=False,
            ),
        ]
    )
    db_session.commit()

    body = client.post(f"/api/v1/profiles/{profile_id}/doctor-visit/generate").text
    assert "CANDIDATE-ONLY-SECRET" not in body
    assert "REJECTED-CANDIDATE-ONLY-SECRET" not in body
    assert "CHAT-PENDING-ONLY-SECRET" not in body
    assert "CHAT-REJECTED-ONLY-SECRET" not in body


def test_empty_profile_returns_explicit_empty_sections_and_no_invention(
    client: TestClient, user: User
) -> None:
    profile_id = create_profile(client, user, "Empty visit profile")
    response = client.post(f"/api/v1/profiles/{profile_id}/doctor-visit/generate")
    assert response.status_code == 200
    brief = response.json()
    for key in (
        "known_history",
        "recent_changes",
        "medications",
        "recent_labs",
        "recent_measurements",
        "recent_symptoms",
        "missing_evidence",
        "questions_to_discuss",
    ):
        assert brief[key] == []
    assert brief["overview_source"] == "TEMPLATE"
    assert "0 known history item(s)" in brief["overview"]


def test_invalid_profile_and_profile_isolation(
    client: TestClient, db_session: Session, user: User
) -> None:
    first = create_profile(client, user, "First")
    second = create_profile(client, user, "Second")
    seed_complete_brief(db_session, first, reference=date.today())
    db_session.add(
        HealthEvent(
            profile_id=second,
            event_type=HealthEventType.CONDITION,
            event_date=date.today(),
            title="SECOND-PROFILE-ONLY",
            verification_status=VerificationStatus.VERIFIED,
            provenance=ProvenanceType.USER_REPORTED,
        )
    )
    db_session.commit()

    first_body = client.post(f"/api/v1/profiles/{first}/doctor-visit/generate").text
    second_body = client.post(f"/api/v1/profiles/{second}/doctor-visit/generate").text
    assert "SECOND-PROFILE-ONLY" not in first_body
    assert "Diabetes" not in second_body
    missing = client.post("/api/v1/profiles/not-a-profile/doctor-visit/generate")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "PROFILE_NOT_FOUND"


def test_generation_only_mutates_append_only_audit(
    client: TestClient, db_session: Session, user: User
) -> None:
    profile_id = create_profile(client, user)
    seed_complete_brief(db_session, profile_id, reference=date.today())
    models = (HealthEvent, Medication, Observation, Symptom, SourceDocument, EvidenceLink)
    before = {model: db_session.scalar(select(func.count()).select_from(model)) for model in models}
    audit_before = db_session.scalar(select(func.count()).select_from(AuditLog))

    response = client.post(f"/api/v1/profiles/{profile_id}/doctor-visit/generate")
    assert response.status_code == 200
    after = {model: db_session.scalar(select(func.count()).select_from(model)) for model in models}
    audit_after = db_session.scalar(select(func.count()).select_from(AuditLog))

    assert after == before
    assert audit_after == audit_before + 1
    audit = db_session.scalar(
        select(AuditLog)
        .where(AuditLog.action == "DOCTOR_VISIT_BRIEF_GENERATED")
        .order_by(AuditLog.created_at.desc())
    )
    assert audit is not None
    assert audit.after_state["profile_id"] == profile_id
    assert "Diabetes" not in json.dumps(audit.after_state)


class RewriteLLM(FakeLLMProvider):
    def __init__(self, mode: str) -> None:
        super().__init__()
        self.mode = mode

    def generate_structured(self, prompt: str, schema: dict[str, object]) -> str:
        del schema
        fingerprint = re.search(r"FACTS_FINGERPRINT: ([a-f0-9]+)", prompt)
        overview = re.search(r"OVERVIEW: (.+)\nFACTS:", prompt)
        assert fingerprint and overview
        text = overview.group(1)
        if self.mode == "fact-change":
            text += " HbA1c 8.1%."
        if self.mode == "unsafe":
            text += " You should increase metformin."
        return json.dumps({"overview": text, "facts_fingerprint": fingerprint.group(1)})


def test_optional_llm_unavailable_and_fact_change_fall_back(
    client: TestClient, db_session: Session, user: User
) -> None:
    profile_id = create_profile(client, user)
    seed_complete_brief(db_session, profile_id, reference=date.today())
    unavailable = FakeLLMProvider()
    unavailable.available = False
    result = DoctorVisitService(unavailable).generate(
        db_session, profile_id, include_llm_rewrite=True
    )
    assert result.rewrite_status == "UNAVAILABLE"
    assert result.overview_source == "TEMPLATE"

    changed = DoctorVisitService(RewriteLLM("fact-change")).generate(
        db_session, profile_id, include_llm_rewrite=True
    )
    assert changed.rewrite_status == "REJECTED_FACT_CHANGE"
    assert changed.overview_source == "TEMPLATE"
    assert "8.1" not in changed.overview
    hba1c = next(item for item in changed.recent_labs if item.name == "HbA1c")
    assert hba1c.value == "7.2"


def test_unsafe_llm_rewrite_is_blocked_and_audited(
    client: TestClient, db_session: Session, user: User
) -> None:
    profile_id = create_profile(client, user)
    result = DoctorVisitService(RewriteLLM("unsafe")).generate(
        db_session, profile_id, include_llm_rewrite=True
    )
    assert result.rewrite_status == "REJECTED_SAFETY"
    assert result.overview_source == "TEMPLATE"
    assert "increase metformin" not in result.overview.lower()
    assert (
        db_session.scalar(
            select(func.count()).select_from(AuditLog).where(AuditLog.action == "SAFETY_BLOCK")
        )
        == 1
    )
