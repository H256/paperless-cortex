"""add_document_pending_tags

Revision ID: aa91f0b6c2d1
Revises: f1a2b3c4d5e6
Create Date: 2026-02-10 20:15:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "aa91f0b6c2d1"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_pending_tags",
        sa.Column("doc_id", sa.Integer(), nullable=False),
        sa.Column("names_json", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["doc_id"], ["documents.id"]),
        sa.PrimaryKeyConstraint("doc_id"),
    )
    op.create_index("ix_document_pending_tags_doc_id", "document_pending_tags", ["doc_id"])


def downgrade() -> None:
    op.drop_index("ix_document_pending_tags_doc_id", table_name="document_pending_tags")
    op.drop_table("document_pending_tags")

