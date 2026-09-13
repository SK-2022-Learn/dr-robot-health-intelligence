"""Phase 10 permission, deterministic pattern, evidence, and isolation tests."""

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.enums import (
    AccessLevel,
    DocumentStatus,
    HealthEventType,
    ProvenanceType,
    RelationshipType,
    VerificationStatus,
)
from app.database.models import (
    AuditLog,
    ConsentPermission,
    EvidenceLink,
    FamilyRelationship,
    HealthEvent,
    HealthProfile,
    SourceDocument,
    User,
)
from app.schemas.profile import ProfileCreate
from app.services.profile import ProfileService


def add_profile(
    db: Session,
    user: User,
    name: str,
    relationship: RelationshipType,
    access: AccessLevel,
) -> HealthProfile:
    return ProfileService().create_profile(
        db,
        ProfileCreate(
            owner_user_id=user.id,
            display_name=name,
            relationship_to_owner=relationship,
            access_level=access,
        ),
    )


def add_condition(
    db: Session,
    profile: HealthProfile,
    title: str,
    *,
    source_document_id: str | None = None,
) -> HealthEvent:
    event = HealthEvent(
        profile_id=profile.id,
        event_type=HealthEventType.CONDITION,
        event_date=date(2020, 1, 1),
        title=title,
        verification_status=VerificationStatus.VERIFIED,
        provenance=ProvenanceType.DOCUMENT_VERIFIED,
        source_document_id=source_document_id,
        created_by_user_id=profile.owner_user_id,
    )
    db.add(event)
    db.flush()
    return event


def family_fixture(db: Session, user: User) -> dict[str, object]:
    profiles: dict[str, object] = {
        "self": add_profile(
            db, user, "Actual self name", RelationshipType.SELF, AccessLevel.PRIVATE
        ),
        "grandparent": add_profile(
            db,
            user,
            "Actual grandparent name",
            RelationshipType.GRANDMOTHER,
            AccessLevel.FULL,
        ),
        "parent": add_profile(
            db, user, "Actual parent name", RelationshipType.MOTHER, AccessLevel.FULL
        ),
        "summary": add_profile(
            db,
            user,
            "Actual summary name",
            RelationshipType.SIBLING,
            AccessLevel.FAMILY_SUMMARY,
        ),
        "private": add_profile(
            db,
            user,
            "Secret sibling name",
            RelationshipType.SIBLING,
            AccessLevel.PRIVATE,
        ),
        "caregiver": add_profile(
            db, user, "Actual child name", RelationshipType.CHILD, AccessLevel.CAREGIVER
        ),
    }
    self_profile = profiles["self"]
    parent = profiles["parent"]
    grandparent = profiles["grandparent"]
    private = profiles["private"]
    db.add_all(
        [
            FamilyRelationship(
                source_profile_id=self_profile.id,
                target_profile_id=parent.id,
                relationship_type=RelationshipType.MOTHER,
            ),
            FamilyRelationship(
                source_profile_id=parent.id,
                target_profile_id=grandparent.id,
                relationship_type=RelationshipType.MOTHER,
            ),
            FamilyRelationship(
                source_profile_id=self_profile.id,
                target_profile_id=private.id,
                relationship_type=RelationshipType.SIBLING,
            ),
        ]
    )
    for key in ("grandparent", "parent", "summary", "private", "caregiver"):
        profile = profiles[key]
        grant = ConsentPermission(
            profile_id=profile.id,
            grantee_user_id=user.id,
            access_level=profile.access_level,
            scope="family-health",
        )
        db.add(grant)
        profiles[f"{key}_grant"] = grant
    db.flush()

    document = SourceDocument(
        profile_id=grandparent.id,
        original_filename="family-source.txt",
        stored_filename="family-source-test.txt",
        mime_type="text/plain",
        storage_path="tests/family-source.txt",
        status=DocumentStatus.PARSED,
    )
    db.add(document)
    db.flush()
    grandparent_event = add_condition(db, grandparent, "Diabetes", source_document_id=document.id)
    db.add(
        EvidenceLink(
            health_event_id=grandparent_event.id,
            source_document_id=document.id,
            page_number=1,
            source_excerpt="Documented diabetes",
        )
    )
    add_condition(db, parent, "  diabetes ")
    add_condition(db, self_profile, "Diabetes")
    add_condition(db, profiles["summary"], "Diabetes")
    add_condition(db, private, "Diabetes")
    add_condition(db, private, "Hypertension")
    add_condition(db, parent, "Hypertension")
    add_condition(db, parent, "Thyroid condition")
    db.commit()
    return profiles


def params(user: User, selected: HealthProfile) -> dict[str, str]:
    return {"requester_user_id": user.id, "selected_profile_id": selected.id}


def test_family_graph_redacts_private_and_never_returns_raw_profile_fields(
    client: TestClient, db_session: Session, user: User
) -> None:
    rows = family_fixture(db_session, user)
    response = client.get("/api/v1/family", params=params(user, rows["self"]))
    assert response.status_code == 200
    body = response.json()
    private = next(row for row in body["profiles"] if row["profile_id"] == rows["private"].id)
    assert private["label"].startswith("Sibling")
    assert private["is_private"] is True
    assert private["documented_condition_count"] is None
    assert private["shared_conditions"] is None
    forbidden = {"display_name", "date_of_birth", "sex", "owner_user_id", "conditions"}
    assert not forbidden.intersection(private)
    assert "Hypertension" not in response.text
    assert client.get(f"/api/v1/profiles/{rows['self'].id}/family").status_code == 404


def test_repeated_condition_generation_branch_states_and_private_isolation(
    client: TestClient, db_session: Session, user: User
) -> None:
    rows = family_fixture(db_session, user)
    before_events = db_session.scalar(select(func.count()).select_from(HealthEvent))
    response = client.get("/api/v1/family/patterns", params=params(user, rows["self"]))
    assert response.status_code == 200
    patterns = response.json()["patterns"]
    assert [row["condition_name"].casefold() for row in patterns] == ["diabetes"]
    pattern = patterns[0]
    assert pattern["profile_count"] == 4
    assert pattern["permitted_profile_count"] == 5
    assert pattern["generation_count"] == 3
    assert pattern["branches"] == ["maternal", "self/children"]
    assert pattern["confidence"] == "MODERATE"
    assert "Hypertension" not in response.text
    private = next(
        row for row in pattern["profile_states"] if row["profile_id"] == rows["private"].id
    )
    unknown = next(
        row for row in pattern["profile_states"] if row["profile_id"] == rows["caregiver"].id
    )
    assert private["state"] == "PRIVATE"
    assert private["health_event_id"] is None
    assert private["evidence"] == []
    assert unknown["state"] == "UNKNOWN"
    assert db_session.scalar(select(func.count()).select_from(HealthEvent)) == before_events


def test_family_summary_hides_detail_while_full_and_caregiver_allow_detail(
    client: TestClient, db_session: Session, user: User
) -> None:
    rows = family_fixture(db_session, user)
    body = client.get(
        "/api/v1/family/patterns/Diabetes/contributors",
        params=params(user, rows["self"]),
    ).json()
    contributors = {row["profile_id"]: row for row in body["patterns"][0]["contributing_profiles"]}
    summary = contributors[rows["summary"].id]
    full = contributors[rows["grandparent"].id]
    assert summary["state"] == "DOCUMENTED"
    assert summary["health_event_id"] is None
    assert summary["verification_status"] is None
    assert summary["evidence"] == []
    assert full["health_event_id"]
    assert full["verification_status"] == "VERIFIED"
    assert full["evidence"][0]["evidence_path"].endswith(full["health_event_id"])

    add_condition(db_session, rows["caregiver"], "Diabetes")
    db_session.commit()
    refreshed = client.get("/api/v1/family/patterns", params=params(user, rows["self"])).json()[
        "patterns"
    ][0]
    caregiver = next(
        row
        for row in refreshed["contributing_profiles"]
        if row["profile_id"] == rows["caregiver"].id
    )
    assert caregiver["health_event_id"]
    assert caregiver["verification_status"] == "VERIFIED"


def test_unknown_and_not_documented_remain_distinct_from_private(
    client: TestClient, db_session: Session, user: User
) -> None:
    rows = family_fixture(db_session, user)
    add_condition(db_session, rows["self"], "Asthma")
    add_condition(db_session, rows["grandparent"], "Asthma")
    db_session.commit()
    patterns = client.get("/api/v1/family/patterns", params=params(user, rows["self"])).json()[
        "patterns"
    ]
    asthma = next(row for row in patterns if row["condition_name"] == "Asthma")
    states = {row["profile_id"]: row["state"] for row in asthma["profile_states"]}
    assert states[rows["parent"].id] == "NOT_DOCUMENTED"
    assert states[rows["caregiver"].id] == "UNKNOWN"
    assert states[rows["private"].id] == "PRIVATE"
    assert "ABSENT" not in states.values()


def test_single_condition_not_shared_and_filters_are_deterministic(
    client: TestClient, db_session: Session, user: User
) -> None:
    rows = family_fixture(db_session, user)
    query = params(user, rows["self"])
    shared = client.get("/api/v1/family/shared-conditions", params=query).json()
    assert len(shared["patterns"]) == 1
    assert "Thyroid condition" not in str(shared)
    assert (
        client.get(
            "/api/v1/family/patterns",
            params={**query, "condition": "thyroid condition"},
        ).json()["patterns"]
        == []
    )
    maternal = client.get("/api/v1/family/patterns", params={**query, "branch": "maternal"}).json()[
        "patterns"
    ]
    assert len(maternal) == 1
    assert (
        client.get("/api/v1/family/patterns", params={**query, "branch": "paternal"}).json()[
            "patterns"
        ]
        == []
    )


def test_permission_change_updates_patterns_and_writes_safe_audit(
    client: TestClient, db_session: Session, user: User
) -> None:
    rows = family_fixture(db_session, user)
    grant = rows["summary_grant"]
    response = client.patch(
        f"/api/v1/family/permissions/{grant.id}",
        json={"requester_user_id": user.id, "access_level": "PRIVATE"},
    )
    assert response.status_code == 200
    assert response.json()["access_level"] == "PRIVATE"
    pattern = client.get("/api/v1/family/patterns", params=params(user, rows["self"])).json()[
        "patterns"
    ][0]
    assert pattern["profile_count"] == 3
    audit = db_session.scalar(
        select(AuditLog).where(AuditLog.action == "FAMILY_PERMISSION_CHANGED")
    )
    assert audit.before_state == {"access_level": "FAMILY_SUMMARY"}
    assert audit.after_state == {"access_level": "PRIVATE"}
    assert "condition" not in str(audit.before_state).casefold()


def test_requester_is_explicit_and_cross_owner_access_is_denied(
    client: TestClient, db_session: Session, user: User
) -> None:
    rows = family_fixture(db_session, user)
    missing = client.get("/api/v1/family", params={"selected_profile_id": rows["self"].id})
    assert missing.status_code == 422
    denied = client.get(
        "/api/v1/family",
        params={
            "selected_profile_id": rows["self"].id,
            "requester_user_id": "other",
        },
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "FAMILY_ACCESS_DENIED"
