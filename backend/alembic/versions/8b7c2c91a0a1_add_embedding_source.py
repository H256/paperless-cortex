"""add_embedding_source

Revision ID: 8b7c2c91a0a1
Revises: 7e0af35a82d3
Create Date: 2026-02-03 09:05:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "8b7c2c91a0a1"
down_revision = "7e0af35a82d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "document_embeddings",
        sa.Column("embedding_source", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("document_embeddings", "embedding_source")
