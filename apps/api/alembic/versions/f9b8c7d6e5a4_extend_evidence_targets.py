"""extend evidence links to medication and symptom targets

Revision ID: f9b8c7d6e5a4
Revises: e8a7b6c5d4f3
Create Date: 2026-09-13 03:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f9b8c7d6e5a4"
down_revision: str | None = "e8a7b6c5d4f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("evidence_links", schema=None) as batch_op:
        batch_op.drop_constraint("ck_evidence_has_target", type_="check")
        batch_op.add_column(sa.Column("medication_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("symptom_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_evidence_links_medication_id_medications", "medications", ["medication_id"], ["id"]
        )
        batch_op.create_foreign_key(
            "fk_evidence_links_symptom_id_symptoms", "symptoms", ["symptom_id"], ["id"]
        )
        batch_op.create_check_constraint(
            "ck_evidence_has_target",
            "health_event_id IS NOT NULL OR observation_id IS NOT NULL "
            "OR medication_id IS NOT NULL OR symptom_id IS NOT NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("evidence_links", schema=None) as batch_op:
        batch_op.drop_constraint("ck_evidence_has_target", type_="check")
        batch_op.drop_constraint("fk_evidence_links_symptom_id_symptoms", type_="foreignkey")
        batch_op.drop_constraint("fk_evidence_links_medication_id_medications", type_="foreignkey")
        batch_op.drop_column("symptom_id")
        batch_op.drop_column("medication_id")
        batch_op.create_check_constraint(
            "ck_evidence_has_target",
            "health_event_id IS NOT NULL OR observation_id IS NOT NULL",
        )
