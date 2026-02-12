"""rename hierarchy json columns to text

Revision ID: 6f4c2d1a9b7e
Revises: d4b8f3a1e77c
Create Date: 2026-02-12 21:55:00
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "6f4c2d1a9b7e"
down_revision = "d4b8f3a1e77c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("document_page_notes", "notes_json", new_column_name="notes_text")
    op.alter_column("document_section_summaries", "summary_json", new_column_name="summary_text")


def downgrade() -> None:
    op.alter_column("document_page_notes", "notes_text", new_column_name="notes_json")
    op.alter_column("document_section_summaries", "summary_text", new_column_name="summary_json")

