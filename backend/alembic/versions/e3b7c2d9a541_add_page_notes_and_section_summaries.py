"""add_page_notes_and_section_summaries

Revision ID: e3b7c2d9a541
Revises: d12f9a4c7e31
Create Date: 2026-02-10 12:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "e3b7c2d9a541"
down_revision = "d12f9a4c7e31"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_page_notes",
        sa.Column("doc_id", sa.Integer(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("notes_json", sa.Text(), nullable=True),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(length=64), nullable=True),
        sa.Column("processed_at", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["doc_id"], ["documents.id"]),
        sa.PrimaryKeyConstraint("doc_id", "page", "source"),
    )
    op.create_table(
        "document_section_summaries",
        sa.Column("doc_id", sa.Integer(), nullable=False),
        sa.Column("section_key", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("summary_json", sa.Text(), nullable=True),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(length=64), nullable=True),
        sa.Column("processed_at", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["doc_id"], ["documents.id"]),
        sa.PrimaryKeyConstraint("doc_id", "section_key", "source"),
    )


def downgrade() -> None:
    op.drop_table("document_section_summaries")
    op.drop_table("document_page_notes")

