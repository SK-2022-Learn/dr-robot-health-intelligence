"""add daily chat pending memory

Revision ID: e8a7b6c5d4f3
Revises: d4e6f8a1b2c3
Create Date: 2026-09-13 02:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e8a7b6c5d4f3"
down_revision: str | None = "d4e6f8a1b2c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

pending_status = sa.Enum(
    "PENDING_REVIEW",
    "NEEDS_CLARIFICATION",
    "CONFIRMED",
    "REJECTED",
    name="pendinghealthentrystatus",
    native_enum=False,
)


def upgrade() -> None:
    op.create_table(
        "pending_health_entries",
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("message_id", sa.String(length=36), nullable=False),
        sa.Column("profile_id", sa.String(length=36), nullable=False),
        sa.Column("structured_data", sa.JSON(), nullable=False),
        sa.Column("original_structured_data", sa.JSON(), nullable=False),
        sa.Column("status", pending_status, nullable=False),
        sa.Column("was_corrected", sa.Boolean(), nullable=False),
        sa.Column("trusted_records", sa.JSON(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"]),
        sa.ForeignKeyConstraint(["profile_id"], ["health_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id"),
    )
    with op.batch_alter_table("pending_health_entries", schema=None) as batch_op:
        batch_op.create_index(
            "ix_pending_conversation_created",
            ["conversation_id", "created_at"],
            unique=False,
        )
        batch_op.create_index("ix_pending_profile_status", ["profile_id", "status"], unique=False)

    with op.batch_alter_table("observations", schema=None) as batch_op:
        batch_op.add_column(sa.Column("source_message_id", sa.String(length=36)))
        batch_op.create_foreign_key(
            "fk_observations_source_message_id_messages",
            "messages",
            ["source_message_id"],
            ["id"],
        )
        batch_op.create_index(
            batch_op.f("ix_observations_source_message_id"),
            ["source_message_id"],
            unique=False,
        )

    with op.batch_alter_table("symptoms", schema=None) as batch_op:
        batch_op.add_column(sa.Column("source_message_id", sa.String(length=36)))
        batch_op.create_foreign_key(
            "fk_symptoms_source_message_id_messages",
            "messages",
            ["source_message_id"],
            ["id"],
        )
        batch_op.create_index(
            batch_op.f("ix_symptoms_source_message_id"),
            ["source_message_id"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("symptoms", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_symptoms_source_message_id"))
        batch_op.drop_constraint("fk_symptoms_source_message_id_messages", type_="foreignkey")
        batch_op.drop_column("source_message_id")

    with op.batch_alter_table("observations", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_observations_source_message_id"))
        batch_op.drop_constraint("fk_observations_source_message_id_messages", type_="foreignkey")
        batch_op.drop_column("source_message_id")

    op.drop_table("pending_health_entries")
