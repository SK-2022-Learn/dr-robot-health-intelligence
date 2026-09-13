"""Future-facing consent grants without an authorization engine."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.database.enums import AccessLevel

if TYPE_CHECKING:
    from app.database.models.health_profile import HealthProfile
    from app.database.models.user import User


class ConsentPermission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "consent_permissions"
    __table_args__ = (
        CheckConstraint(
            "grantee_user_id IS NOT NULL OR grantee_profile_id IS NOT NULL",
            name="ck_permission_has_grantee",
        ),
    )

    profile_id: Mapped[str] = mapped_column(ForeignKey("health_profiles.id"), index=True)
    grantee_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    grantee_profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("health_profiles.id"), nullable=True
    )
    access_level: Mapped[AccessLevel] = mapped_column(Enum(AccessLevel, native_enum=False))
    scope: Mapped[str | None] = mapped_column(String(250), nullable=True)

    profile: Mapped[HealthProfile] = relationship(
        foreign_keys=[profile_id], back_populates="permissions"
    )
    grantee_user: Mapped[User | None] = relationship(foreign_keys=[grantee_user_id])
    grantee_profile: Mapped[HealthProfile | None] = relationship(foreign_keys=[grantee_profile_id])
