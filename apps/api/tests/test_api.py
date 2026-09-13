"""Phase 2/3 API contracts, failures, isolation, and audit visibility."""

from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database.enums import (
    AccessLevel,
    DocumentStatus,
    ProvenanceType,
    RelationshipType,
    VerificationStatus,
)
from app.database.models import (
    FamilyRelationship,
    Medication,
    Observation,
    SourceDocument,
    Symptom,
    User,
)
from app.repositories.user import UserRepository
from app.schemas.profile import ProfileCreate
from app.schemas.user import UserCreate
from app.services.profile import ProfileService


def create_profile(client: TestClient, user: User) -> dict[str, object]:
    response = client.post(
        "/api/v1/profiles",
        json={
            "owner_user_id": user.id,
            "display_name": "API profile",
            "relationship_to_owner": "SELF",
            "access_level": "PRIVATE",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_profile_api_crud(client: TestClient, user: User) -> None:
    profile = create_profile(client, user)
    profile_id = profile["id"]

    listing = client.get("/api/v1/profiles")
    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()] == [profile_id]

    retrieved = client.get(f"/api/v1/profiles/{profile_id}")
    assert retrieved.status_code == 200
    assert retrieved.json()["display_name"] == "API profile"

    updated = client.patch(
        f"/api/v1/profiles/{profile_id}", json={"display_name": "Updated API profile"}
    )
    assert updated.status_code == 200
    assert updated.json()["display_name"] == "Updated API profile"


def test_health_event_api_and_audit(client: TestClient, user: User) -> None:
    profile_id = create_profile(client, user)["id"]
    created = client.post(
        f"/api/v1/profiles/{profile_id}/events",
        json={
            "event_type": "CONDITION",
            "event_date": "2021-02-03",
            "title": "Fictional event",
            "provenance": "USER_REPORTED",
            "verification_status": "PENDING",
            "created_by_user_id": user.id,
        },
    )
    assert created.status_code == 201
    event_id = created.json()["id"]

    listing = client.get(f"/api/v1/profiles/{profile_id}/events")
    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()] == [event_id]

    retrieved = client.get(f"/api/v1/events/{event_id}")
    assert retrieved.status_code == 200
    assert retrieved.json()["title"] == "Fictional event"

    updated = client.patch(
        f"/api/v1/events/{event_id}",
        json={
            "title": "Reviewed fictional event",
            "provenance": "USER_CORRECTED",
            "verification_status": "VERIFIED",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Reviewed fictional event"

    audit = client.get("/api/v1/audit", params={"entity_id": event_id})
    assert audit.status_code == 200
    assert {row["action"] for row in audit.json()} == {
        "health_event.created",
        "health_event.updated",
    }


def test_not_found_and_malformed_input(client: TestClient, user: User) -> None:
    missing_profile = client.get("/api/v1/profiles/not-a-real-id")
    assert missing_profile.status_code == 404
    assert missing_profile.json()["error"]["code"] == "PROFILE_NOT_FOUND"
    assert missing_profile.json()["error"]["request_id"]

    missing_event = client.get("/api/v1/events/not-a-real-id")
    assert missing_event.status_code == 404
    assert missing_event.json()["error"]["code"] == "HEALTH_EVENT_NOT_FOUND"

    malformed = client.post(
        "/api/v1/profiles",
        json={"owner_user_id": user.id, "display_name": "", "access_level": "NOT_VALID"},
    )
    assert malformed.status_code == 422

    missing_owner = client.post(
        "/api/v1/profiles",
        json={"owner_user_id": "missing", "display_name": "No owner"},
    )
    assert missing_owner.status_code == 404
    assert missing_owner.json()["error"]["code"] == "USER_NOT_FOUND"


def test_profile_data_read_endpoints(client: TestClient, db_session: Session, user: User) -> None:
    profile_id = create_profile(client, user)["id"]
    db_session.add_all(
        [
            Observation(
                profile_id=profile_id,
                display_name="Fictional value",
                value_text="Available",
                observed_at=datetime.now(UTC),
                provenance=ProvenanceType.USER_REPORTED,
                verification_status=VerificationStatus.PENDING,
            ),
            Medication(
                profile_id=profile_id,
                name="Fictional medication",
                is_active=True,
                provenance=ProvenanceType.USER_REPORTED,
                verification_status=VerificationStatus.PENDING,
            ),
            Symptom(
                profile_id=profile_id,
                name="Fictional symptom",
                provenance=ProvenanceType.USER_REPORTED,
                verification_status=VerificationStatus.PENDING,
            ),
            SourceDocument(
                profile_id=profile_id,
                original_filename="fictional.pdf",
                stored_filename="isolated-fictional.pdf",
                mime_type="application/pdf",
                storage_path="private/not-exposed.pdf",
                document_date=date(2026, 1, 1),
                status=DocumentStatus.UPLOADED,
                extracted_text="must not be exposed",
            ),
        ]
    )
    db_session.commit()

    for resource in ("observations", "medications", "symptoms", "documents"):
        response = client.get(f"/api/v1/profiles/{profile_id}/{resource}")
        assert response.status_code == 200
        assert len(response.json()) == 1

    document = client.get(f"/api/v1/profiles/{profile_id}/documents").json()[0]
    assert "storage_path" not in document
    assert "extracted_text" not in document

    empty_profile_id = create_profile(client, user)["id"]
    assert client.get(f"/api/v1/profiles/{empty_profile_id}/observations").json() == []

    missing = client.get("/api/v1/profiles/missing/observations")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "PROFILE_NOT_FOUND"


def test_family_endpoint_preserves_owner_isolation(
    client: TestClient, db_session: Session, user: User
) -> None:
    selected = ProfileService().create_profile(
        db_session,
        ProfileCreate(owner_user_id=user.id, display_name="Selected"),
    )
    relative = ProfileService().create_profile(
        db_session,
        ProfileCreate(
            owner_user_id=user.id,
            display_name="Relative",
            relationship_to_owner=RelationshipType.SIBLING,
            access_level=AccessLevel.FAMILY_SUMMARY,
        ),
    )
    other_user = UserRepository().create(db_session, UserCreate(username="other-owner"))
    db_session.commit()
    ProfileService().create_profile(
        db_session, ProfileCreate(owner_user_id=other_user.id, display_name="Other family")
    )
    db_session.add(
        FamilyRelationship(
            source_profile_id=selected.id,
            target_profile_id=relative.id,
            relationship_type=RelationshipType.SIBLING,
        )
    )
    db_session.commit()

    response = client.get(
        "/api/v1/family",
        params={"selected_profile_id": selected.id, "requester_user_id": user.id},
    )
    assert response.status_code == 200
    body = response.json()
    assert {profile["label"] for profile in body["profiles"]} == {"Self", "Sibling"}
    assert all("display_name" not in profile for profile in body["profiles"])
    assert len(body["relationships"]) == 1


def test_safe_system_status(client: TestClient) -> None:
    response = client.get("/api/v1/system")

    assert response.status_code == 200
    body = response.json()
    assert body["environment"] == "development"
    assert body["database"] == "connected"
    assert body["upload_directory"] == "configured"
    assert body["vector_provider"] == "Pinecone"
    assert body["vector_status"] == "connected"
    assert body["vector_dimension"] == 3
    assert body["vector_metric"] == "cosine"
    assert body["vector_count"] == 0
    assert body["embedding_provider"] == "Ollama"
    assert body["embedding_status"] == "connected"
    assert body["embedding_dimension"] == 3
    assert body["compatibility"] == "compatible"
    assert body["llm_provider"] == "Ollama"
    assert body["llm"] == "connected"
    assert isinstance(body["vector_index"], str) and body["vector_index"]
    assert isinstance(body["embedding_model"], str) and body["embedding_model"]
    assert isinstance(body["llm_model"], str) and body["llm_model"]
