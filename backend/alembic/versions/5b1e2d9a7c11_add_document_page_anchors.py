"""add_document_page_anchors

Revision ID: 5b1e2d9a7c11
Revises: 6f4c2d1a9b7e
Create Date: 2026-02-14 23:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "5b1e2d9a7c11"
down_revision = "6f4c2d1a9b7e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_page_anchors",
        sa.Column("doc_id", sa.Integer(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("anchors_json", sa.Text(), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(length=64), nullable=True),
        sa.Column("processed_at", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["doc_id"], ["documents.id"]),
        sa.PrimaryKeyConstraint("doc_id", "page", "source"),
    )


def downgrade() -> None:
    op.drop_table("document_page_anchors")
