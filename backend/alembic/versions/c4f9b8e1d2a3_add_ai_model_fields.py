"""add_ai_model_fields

Revision ID: c4f9b8e1d2a3
Revises: 0132c6a5422e
Create Date: 2026-02-02 10:30:00.000000
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "c4f9b8e1d2a3"
down_revision = "0132c6a5422e"
branch_labels = None
# This revision ALTERs document_suggestions / document_page_texts, which are
# created on the sibling branch that ends at 2f6e9b1a3c4d (add_suggestion_audit,
# the tip of the add_document_suggestions / add_document_page_texts chain).
# Without this explicit dependency, a fresh `alembic upgrade head` runs this
# revision before those tables exist and fails with "no such table".
depends_on = "2f6e9b1a3c4d"


def upgrade() -> None:
    op.add_column("documents", sa.Column("analysis_model", sa.String(length=128), nullable=True))
    op.add_column("documents", sa.Column("analysis_processed_at", sa.String(length=64), nullable=True))
    op.add_column("document_suggestions", sa.Column("model_name", sa.String(length=128), nullable=True))
    op.add_column("document_suggestions", sa.Column("processed_at", sa.String(length=64), nullable=True))
    op.add_column("document_page_texts", sa.Column("model_name", sa.String(length=128), nullable=True))
    op.add_column("document_page_texts", sa.Column("processed_at", sa.String(length=64), nullable=True))
    op.execute("UPDATE document_suggestions SET processed_at = created_at WHERE processed_at IS NULL")
    op.execute("UPDATE document_page_texts SET processed_at = created_at WHERE processed_at IS NULL")


def downgrade() -> None:
    op.drop_column("document_page_texts", "processed_at")
    op.drop_column("document_page_texts", "model_name")
    op.drop_column("document_suggestions", "processed_at")
    op.drop_column("document_suggestions", "model_name")
    op.drop_column("documents", "analysis_processed_at")
    op.drop_column("documents", "analysis_model")
