"""add_clean_text_fields_to_page_texts

Revision ID: d12f9a4c7e31
Revises: 8b7c2c91a0a1, 9c6d2c1b1a44
Create Date: 2026-02-10 11:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d12f9a4c7e31"
down_revision = ("8b7c2c91a0a1", "9c6d2c1b1a44")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("document_page_texts", sa.Column("raw_text", sa.Text(), nullable=True))
    op.add_column("document_page_texts", sa.Column("clean_text", sa.Text(), nullable=True))
    op.add_column("document_page_texts", sa.Column("token_estimate_raw", sa.Integer(), nullable=True))
    op.add_column("document_page_texts", sa.Column("token_estimate_clean", sa.Integer(), nullable=True))
    op.add_column("document_page_texts", sa.Column("cleaned_at", sa.String(length=64), nullable=True))
    op.execute("UPDATE document_page_texts SET raw_text = text WHERE raw_text IS NULL")
    op.execute("UPDATE document_page_texts SET clean_text = text WHERE clean_text IS NULL")
    op.execute("UPDATE document_page_texts SET cleaned_at = processed_at WHERE cleaned_at IS NULL")


def downgrade() -> None:
    op.drop_column("document_page_texts", "cleaned_at")
    op.drop_column("document_page_texts", "token_estimate_clean")
    op.drop_column("document_page_texts", "token_estimate_raw")
    op.drop_column("document_page_texts", "clean_text")
    op.drop_column("document_page_texts", "raw_text")

