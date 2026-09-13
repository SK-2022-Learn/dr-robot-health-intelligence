"""Isolated health profile for one person in a family context."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.database.enums import AccessLevel, RelationshipType

if TYPE_CHECKING:
    from app.database.models.consent_permission import ConsentPermission
    from app.database.models.conversation import Conversation
    from app.database.models.family_relationship import FamilyRelationship
    from app.database.models.health_event import HealthEvent
    from app.database.models.medication import Medication
    from app.database.models.observation import Observation
    from app.database.models.pending_health_entry import PendingHealthEntry
    from app.database.models.source_document import SourceDocument
    from app.database.models.symptom import Symptom
    from app.database.models.user import User


class HealthProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Stores one person's data separately from every other family member."""

    __tablename__ = "health_profiles"

    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    display_name: Mapped[str] = mapped_column(String(150))
    relationship_to_owner: Mapped[RelationshipType] = mapped_column(
        Enum(RelationshipType, native_enum=False), default=RelationshipType.SELF
    )
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    sex: Mapped[str | None] = mapped_column(String(50), nullable=True)
    access_level: Mapped[AccessLevel] = mapped_column(
        Enum(AccessLevel, native_enum=False), default=AccessLevel.PRIVATE
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    owner: Mapped[User] = relationship(back_populates="profiles")
    health_events: Mapped[list[HealthEvent]] = relationship(back_populates="profile")
    source_documents: Mapped[list[SourceDocument]] = relationship(back_populates="profile")
    observations: Mapped[list[Observation]] = relationship(back_populates="profile")
    medications: Mapped[list[Medication]] = relationship(back_populates="profile")
    symptoms: Mapped[list[Symptom]] = relationship(back_populates="profile")
    conversations: Mapped[list[Conversation]] = relationship(back_populates="profile")
    pending_health_entries: Mapped[list[PendingHealthEntry]] = relationship(
        back_populates="profile"
    )
    outgoing_relationships: Mapped[list[FamilyRelationship]] = relationship(
        foreign_keys="FamilyRelationship.source_profile_id", back_populates="source_profile"
    )
    incoming_relationships: Mapped[list[FamilyRelationship]] = relationship(
        foreign_keys="FamilyRelationship.target_profile_id", back_populates="target_profile"
    )
    permissions: Mapped[list[ConsentPermission]] = relationship(
        foreign_keys="ConsentPermission.profile_id", back_populates="profile"
    )
