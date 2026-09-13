"""Directed relationships between distinct health profiles."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, UUIDPrimaryKeyMixin, utc_now
from app.database.enums import RelationshipType

if TYPE_CHECKING:
    from app.database.models.health_profile import HealthProfile


class FamilyRelationship(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "family_relationships"
    __table_args__ = (
        CheckConstraint(
            "source_profile_id != target_profile_id", name="ck_family_distinct_profiles"
        ),
        UniqueConstraint(
            "source_profile_id",
            "target_profile_id",
            "relationship_type",
            name="uq_family_relationship",
        ),
    )

    source_profile_id: Mapped[str] = mapped_column(ForeignKey("health_profiles.id"))
    target_profile_id: Mapped[str] = mapped_column(ForeignKey("health_profiles.id"))
    relationship_type: Mapped[RelationshipType] = mapped_column(
        Enum(RelationshipType, native_enum=False)
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    source_profile: Mapped[HealthProfile] = relationship(
        foreign_keys=[source_profile_id], back_populates="outgoing_relationships"
    )
    target_profile: Mapped[HealthProfile] = relationship(
        foreign_keys=[target_profile_id], back_populates="incoming_relationships"
    )
