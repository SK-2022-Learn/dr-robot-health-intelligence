"""add document ingestion

Revision ID: 8f42c9d3a1b7
Revises: c7171adadddb
Create Date: 2026-09-12 23:15:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "8f42c9d3a1b7"
down_revision: str | None = "c7171adadddb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

old_status = sa.Enum(
    "PENDING",
    "VERIFIED",
    "REJECTED",
    "NEEDS_REVIEW",
    name="verificationstatus",
    native_enum=False,
)
document_status = sa.Enum(
    "UPLOADED",
    "PROCESSING",
    "PARSED",
    "NEEDS_OCR",
    "FAILED",
    name="documentstatus",
    native_enum=False,
)


def upgrade() -> None:
    op.execute(
        """
        UPDATE source_documents
        SET status = CASE status
            WHEN 'VERIFIED' THEN 'PARSED'
            WHEN 'REJECTED' THEN 'FAILED'
            ELSE 'UPLOADED'
        END
        """
    )
    with op.batch_alter_table("source_documents", schema=None) as batch_op:
        batch_op.alter_column(
            "status", existing_type=old_status, type_=document_status, existing_nullable=False
        )
        batch_op.add_column(
            sa.Column("page_count", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.create_unique_constraint("uq_document_profile_hash", ["profile_id", "file_hash"])

    op.create_table(
        "document_pages",
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["source_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "page_number", name="uq_document_page_number"),
    )
    with op.batch_alter_table("document_pages", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_document_pages_document_id"), ["document_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("document_pages", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_document_pages_document_id"))
    op.drop_table("document_pages")

    op.execute(
        """
        UPDATE source_documents
        SET status = CASE status
            WHEN 'PARSED' THEN 'VERIFIED'
            WHEN 'FAILED' THEN 'REJECTED'
            ELSE 'PENDING'
        END
        """
    )
    with op.batch_alter_table("source_documents", schema=None) as batch_op:
        batch_op.drop_constraint("uq_document_profile_hash", type_="unique")
        batch_op.drop_column("page_count")
        batch_op.alter_column(
            "status", existing_type=document_status, type_=old_status, existing_nullable=False
        )
