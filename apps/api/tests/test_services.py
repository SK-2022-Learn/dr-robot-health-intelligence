"""Service orchestration tests, including atomic audit history."""

from datetime import date

from sqlalchemy.orm import Session

from app.database.enums import (
    AccessLevel,
    HealthEventType,
    ProvenanceType,
    RelationshipType,
    VerificationStatus,
)
from app.database.models import User
from app.schemas.health_event import HealthEventCreate, HealthEventUpdate
from app.schemas.profile import ProfileCreate, ProfileUpdate
from app.services.audit import AuditService
from app.services.health_event import HealthEventService
from app.services.profile import ProfileService


def test_profile_service_crud_and_audit(db_session: Session, user: User) -> None:
    service = ProfileService()
    profile = service.create_profile(
        db_session,
        ProfileCreate(
            owner_user_id=user.id,
            display_name="Service profile",
            relationship_to_owner=RelationshipType.SELF,
            access_level=AccessLevel.PRIVATE,
        ),
    )

    assert service.retrieve_profile(db_session, profile.id).id == profile.id
    assert [item.id for item in service.list_profiles(db_session)] == [profile.id]

    updated = service.update_profile(
        db_session, profile.id, ProfileUpdate(display_name="Updated profile")
    )
    assert updated.display_name == "Updated profile"

    audit_rows = AuditService().list(db_session, entity_type="health_profile", entity_id=profile.id)
    assert {row.action for row in audit_rows} == {"profile.created", "profile.updated"}
    assert (
        next(row for row in audit_rows if row.action == "profile.updated").before_state[
            "display_name"
        ]
        == "Service profile"
    )


def test_health_event_service_crud_and_audit(db_session: Session, user: User) -> None:
    profile = ProfileService().create_profile(
        db_session,
        ProfileCreate(owner_user_id=user.id, display_name="Event profile"),
    )
    service = HealthEventService()
    event = service.create_event(
        db_session,
        profile.id,
        HealthEventCreate(
            event_type=HealthEventType.CONDITION,
            event_date=date(2020, 1, 1),
            title="Fictional condition",
            provenance=ProvenanceType.USER_REPORTED,
            verification_status=VerificationStatus.PENDING,
            created_by_user_id=user.id,
        ),
    )

    assert service.retrieve_event(db_session, event.id).id == event.id
    assert [item.id for item in service.list_profile_events(db_session, profile.id)] == [event.id]

    updated = service.update_event(
        db_session,
        event.id,
        HealthEventUpdate(
            title="Corrected fictional condition",
            provenance=ProvenanceType.USER_CORRECTED,
            verification_status=VerificationStatus.VERIFIED,
        ),
    )
    assert updated.title == "Corrected fictional condition"

    audit_rows = AuditService().list(db_session, entity_type="health_event", entity_id=event.id)
    assert {row.action for row in audit_rows} == {
        "health_event.created",
        "health_event.updated",
    }
