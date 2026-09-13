"""Health-event business rules and atomic audit creation."""

from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.database.enums import ProvenanceType, VerificationStatus
from app.database.models import HealthEvent
from app.repositories.health_event import HealthEventRepository
from app.repositories.profile import ProfileRepository
from app.schemas.health_event import HealthEventCreate, HealthEventRead, HealthEventUpdate
from app.services.audit import AuditService


def _event_state(event: HealthEvent) -> dict[str, object]:
    return HealthEventRead.model_validate(event).model_dump(mode="json")


class HealthEventService:
    def __init__(
        self,
        repository: HealthEventRepository | None = None,
        profiles: ProfileRepository | None = None,
        audit: AuditService | None = None,
    ) -> None:
        self.repository = repository or HealthEventRepository()
        self.profiles = profiles or ProfileRepository()
        self.audit = audit or AuditService()

    @staticmethod
    def _validate_provenance(data: HealthEventCreate | HealthEventUpdate) -> None:
        if (
            data.provenance == ProvenanceType.DOCUMENT_VERIFIED
            and data.verification_status != VerificationStatus.VERIFIED
        ):
            raise ApiError(
                status_code=422,
                code="INVALID_VERIFICATION_STATUS",
                message="Document-verified events must be explicitly marked verified.",
            )

    def create_event(self, db: Session, profile_id: str, data: HealthEventCreate) -> HealthEvent:
        profile = self.profiles.get(db, profile_id)
        if profile is None:
            raise ApiError(
                status_code=404,
                code="PROFILE_NOT_FOUND",
                message="Health profile was not found.",
            )
        self._validate_provenance(data)

        event = self.repository.create(db, profile_id, data)
        self.audit.append(
            db,
            action="health_event.created",
            entity_type="health_event",
            entity_id=event.id,
            actor_user_id=data.created_by_user_id,
            after_state=_event_state(event),
        )
        db.commit()
        db.refresh(event)
        return event

    def retrieve_event(self, db: Session, event_id: str) -> HealthEvent:
        event = self.repository.get(db, event_id)
        if event is None:
            raise ApiError(
                status_code=404,
                code="HEALTH_EVENT_NOT_FOUND",
                message="Health event was not found.",
            )
        return event

    def list_profile_events(self, db: Session, profile_id: str) -> list[HealthEvent]:
        if self.profiles.get(db, profile_id) is None:
            raise ApiError(
                status_code=404,
                code="PROFILE_NOT_FOUND",
                message="Health profile was not found.",
            )
        return self.repository.list_for_profile(db, profile_id)

    def update_event(self, db: Session, event_id: str, data: HealthEventUpdate) -> HealthEvent:
        event = self.retrieve_event(db, event_id)
        before_state = _event_state(event)
        changes = data.model_dump(exclude_unset=True, exclude_none=True)
        if not changes:
            return event

        prospective = HealthEventUpdate(
            provenance=changes.get("provenance", event.provenance),
            verification_status=changes.get("verification_status", event.verification_status),
        )
        self._validate_provenance(prospective)
        event = self.repository.update(db, event, changes)
        self.audit.append(
            db,
            action="health_event.updated",
            entity_type="health_event",
            entity_id=event.id,
            actor_user_id=event.created_by_user_id,
            before_state=before_state,
            after_state=_event_state(event),
        )
        db.commit()
        db.refresh(event)
        return event
