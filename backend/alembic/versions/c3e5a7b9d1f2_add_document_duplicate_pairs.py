"""add_document_duplicate_pairs

Revision ID: c3e5a7b9d1f2
Revises: a7b8c9d0e1f2
Create Date: 2026-10-15 22:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c3e5a7b9d1f2"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_duplicate_pairs",
        sa.Column("doc_a_id", sa.Integer(), sa.ForeignKey("documents.id"), primary_key=True),
        sa.Column("doc_b_id", sa.Integer(), sa.ForeignKey("documents.id"), primary_key=True),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("level", sa.String(length=16), nullable=False),
        sa.Column("embedding_score", sa.Float(), nullable=True),
        sa.Column("text_score", sa.Float(), nullable=True),
        sa.Column("keys_score", sa.Float(), nullable=True),
        sa.Column("meta_score", sa.Float(), nullable=True),
        sa.Column("signals_json", sa.Text(), nullable=True),
        sa.Column("ignored", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("ignored_at", sa.String(length=64), nullable=True),
        sa.Column("scanned_at", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_document_duplicate_pairs_doc_b_id", "document_duplicate_pairs", ["doc_b_id"]
    )
    op.create_index(
        "ix_document_duplicate_pairs_ignored_level",
        "document_duplicate_pairs",
        ["ignored", "level"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_document_duplicate_pairs_ignored_level", table_name="document_duplicate_pairs"
    )
    op.drop_index("ix_document_duplicate_pairs_doc_b_id", table_name="document_duplicate_pairs")
    op.drop_table("document_duplicate_pairs")
