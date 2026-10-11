"""add_document_embedding_pending_reembed

Revision ID: f0e1a2b3c4d5
Revises: a1b2c3d4e5f6
Create Date: 2026-09-28 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "f0e1a2b3c4d5"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "document_embeddings",
        sa.Column(
            "pending_reembed", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )


def downgrade() -> None:
    op.drop_column("document_embeddings", "pending_reembed")
