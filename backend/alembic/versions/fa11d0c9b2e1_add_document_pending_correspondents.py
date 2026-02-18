"""add_document_pending_correspondents

Revision ID: fa11d0c9b2e1
Revises: 5b1e2d9a7c11
Create Date: 2026-02-18 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "fa11d0c9b2e1"
down_revision = "5b1e2d9a7c11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_pending_correspondents",
        sa.Column("doc_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=True),
        sa.Column("updated_at", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["doc_id"], ["documents.id"]),
        sa.PrimaryKeyConstraint("doc_id"),
    )
    op.create_index(
        "ix_document_pending_correspondents_doc_id",
        "document_pending_correspondents",
        ["doc_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_document_pending_correspondents_doc_id", table_name="document_pending_correspondents")
    op.drop_table("document_pending_correspondents")
