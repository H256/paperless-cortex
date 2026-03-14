"""expand_deleted_at_length

Revision ID: b8c1f9e2d4a5
Revises: 7e0af35a82d3
Create Date: 2026-02-03 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "b8c1f9e2d4a5"
down_revision = "7e0af35a82d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "documents",
        "deleted_at",
        existing_type=sa.String(length=64),
        type_=sa.String(length=128),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "documents",
        "deleted_at",
        existing_type=sa.String(length=128),
        type_=sa.String(length=64),
        existing_nullable=True,
    )
