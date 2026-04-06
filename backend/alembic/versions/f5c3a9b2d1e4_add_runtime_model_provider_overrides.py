"""add_runtime_model_provider_overrides

Revision ID: f5c3a9b2d1e4
Revises: b7c4d8e9f1a2
Create Date: 2026-04-06 11:20:00.000000
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "f5c3a9b2d1e4"
down_revision = "b7c4d8e9f1a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "runtime_model_provider_overrides",
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("base_url", sa.String(length=512), nullable=True),
        sa.Column("model", sa.String(length=256), nullable=True),
        sa.Column("api_key_encrypted", sa.Text(), nullable=True),
        sa.Column("api_key_hint", sa.String(length=32), nullable=True),
        sa.Column("updated_at", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("role"),
    )


def downgrade() -> None:
    op.drop_table("runtime_model_provider_overrides")
