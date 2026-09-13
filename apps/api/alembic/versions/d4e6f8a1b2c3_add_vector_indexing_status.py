"""add vector indexing status

Revision ID: d4e6f8a1b2c3
Revises: 8f42c9d3a1b7
Create Date: 2026-09-13 01:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d4e6f8a1b2c3"
down_revision: str | None = "8f42c9d3a1b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

vector_status = sa.Enum(
    "NOT_INDEXED",
    "INDEXING",
    "INDEXED",
    "INDEX_FAILED",
    name="vectorindexstatus",
    native_enum=False,
)


def upgrade() -> None:
    with op.batch_alter_table("source_documents", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "vector_index_status",
                vector_status,
                server_default="NOT_INDEXED",
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("vector_indexed_at", sa.DateTime(timezone=True)))
        batch_op.add_column(
            sa.Column("vector_chunk_count", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.add_column(sa.Column("vector_index_error", sa.String(length=100)))


def downgrade() -> None:
    with op.batch_alter_table("source_documents", schema=None) as batch_op:
        batch_op.drop_column("vector_index_error")
        batch_op.drop_column("vector_chunk_count")
        batch_op.drop_column("vector_indexed_at")
        batch_op.drop_column("vector_index_status")
