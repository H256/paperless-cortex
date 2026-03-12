"""add_document_ocr_scores

Revision ID: 9c6d2c1b1a44
Revises: b8c1f9e2d4a5
Create Date: 2026-02-06 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "9c6d2c1b1a44"
down_revision = "b8c1f9e2d4a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_ocr_scores",
        sa.Column("doc_id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=True),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("verdict", sa.String(length=32), nullable=True),
        sa.Column("components_json", sa.Text(), nullable=True),
        sa.Column("noise_json", sa.Text(), nullable=True),
        sa.Column("ppl_json", sa.Text(), nullable=True),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.String(length=64), nullable=True),
        sa.Column("processed_at", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["doc_id"], ["documents.id"]),
        sa.PrimaryKeyConstraint("doc_id", "source"),
    )


def downgrade() -> None:
    op.drop_table("document_ocr_scores")
