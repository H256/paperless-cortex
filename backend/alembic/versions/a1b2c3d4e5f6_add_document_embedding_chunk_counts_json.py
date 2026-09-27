"""add_document_embedding_chunk_counts_json

Revision ID: a1b2c3d4e5f6
Revises: c6a1b9e2d4f8
Create Date: 2026-09-27 16:30:00.000000
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "c6a1b9e2d4f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "document_embeddings",
        sa.Column("chunk_counts_json", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("document_embeddings", "chunk_counts_json")
