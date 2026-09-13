"""Persistence and validation tests for the Phase 2 domain model."""

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.enums import (
    AccessLevel,
    CandidateStatus,
    DocumentStatus,
    HealthEventType,
    ProvenanceType,
    RelationshipType,
    VerificationStatus,
)
from app.database.models import (
    AuditLog,
    ConsentPermission,
    ExtractedCandidate,
    FamilyRelationship,
    HealthEvent,
    HealthProfile,
    Observation,
    SourceDocument,
    User,
)
from app.schemas.observation import ObservationCreate
from app.schemas.permission import ConsentPermissionCreate


def make_profile(db: Session, user: User, name: str = "Profile") -> HealthProfile:
    profile = HealthProfile(
        owner_user_id=user.id,
        display_name=name,
        relationship_to_owner=RelationshipType.SELF,
        access_level=AccessLevel.PRIVATE,
    )
    db.add(profile)
    db.commit()
    return profile


def test_user_and_profile_creation(db_session: Session, user: User) -> None:
    profile = make_profile(db_session, user, "Family member")

    assert user.username == "test-user"
    assert profile.owner_user_id == user.id
    assert profile.id is not None


def test_family_relationship_constraints(db_session: Session, user: User) -> None:
    source = make_profile(db_session, user, "Source")
    target = make_profile(db_session, user, "Target")
    relationship = FamilyRelationship(
        source_profile_id=source.id,
        target_profile_id=target.id,
        relationship_type=RelationshipType.SIBLING,
    )
    db_session.add(relationship)
    db_session.commit()
    assert relationship.id is not None

    duplicate = FamilyRelationship(
        source_profile_id=source.id,
        target_profile_id=target.id,
        relationship_type=RelationshipType.SIBLING,
    )
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    self_link = FamilyRelationship(
        source_profile_id=source.id,
        target_profile_id=source.id,
        relationship_type=RelationshipType.SELF,
    )
    db_session.add(self_link)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_health_event_and_observation_values(db_session: Session, user: User) -> None:
    profile = make_profile(db_session, user)
    event = HealthEvent(
        profile_id=profile.id,
        event_type=HealthEventType.LAB,
        event_date=date(2026, 1, 1),
        title="Fictional lab",
        provenance=ProvenanceType.USER_REPORTED,
        verification_status=VerificationStatus.PENDING,
    )
    db_session.add(event)
    db_session.flush()
    numeric = Observation(
        profile_id=profile.id,
        health_event_id=event.id,
        display_name="HbA1c",
        value_number=7.2,
        unit="%",
        observed_at=datetime.now(UTC),
        provenance=ProvenanceType.USER_REPORTED,
        verification_status=VerificationStatus.PENDING,
    )
    textual = Observation(
        profile_id=profile.id,
        display_name="Sleep quality",
        value_text="Restful",
        observed_at=datetime.now(UTC),
        provenance=ProvenanceType.USER_REPORTED,
        verification_status=VerificationStatus.PENDING,
    )
    db_session.add_all([numeric, textual])
    db_session.commit()

    assert numeric.value_number == 7.2
    assert textual.value_text == "Restful"
    with pytest.raises(ValidationError):
        ObservationCreate(
            profile_id=profile.id,
            display_name="Missing value",
            observed_at=datetime.now(UTC),
            provenance=ProvenanceType.USER_REPORTED,
        )


def test_candidate_permission_and_audit(db_session: Session, user: User) -> None:
    profile = make_profile(db_session, user)
    document = SourceDocument(
        profile_id=profile.id,
        original_filename="fictional.txt",
        stored_filename="candidate-fictional.txt",
        mime_type="text/plain",
        storage_path="data/demo/fictional.txt",
        status=DocumentStatus.UPLOADED,
    )
    db_session.add(document)
    db_session.flush()
    candidate = ExtractedCandidate(
        document_id=document.id,
        candidate_type="condition",
        raw_text="Fictional raw text",
        structured_data={"name": "Fictional condition"},
        status=CandidateStatus.PENDING,
    )
    permission = ConsentPermission(
        profile_id=profile.id,
        grantee_user_id=user.id,
        access_level=AccessLevel.CAREGIVER,
    )
    audit = AuditLog(
        actor_user_id=user.id,
        action="test.created",
        entity_type="test",
        entity_id=profile.id,
        after_state={"status": "created"},
    )
    db_session.add_all([candidate, permission, audit])
    db_session.commit()

    assert candidate.structured_data["name"] == "Fictional condition"
    assert permission.grantee_user_id == user.id
    assert audit.before_state is None
    with pytest.raises(ValidationError):
        ConsentPermissionCreate(profile_id=profile.id, access_level=AccessLevel.PRIVATE)
