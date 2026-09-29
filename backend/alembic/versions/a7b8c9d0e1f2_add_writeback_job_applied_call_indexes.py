"""Add writeback job applied call indexes.

Revision ID: a7b8c9d0e1f2
Revises: f0e1a2b3c4d5
Create Date: 2026-09-29 08:15:00.000000

Tracks which per-call writeback operations have already been applied so a
replayed job can skip calls that already succeeded (idempotent replay).
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "a7b8c9d0e1f2"
down_revision = "f0e1a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "writeback_jobs",
        sa.Column("applied_call_indexes_json", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("writeback_jobs", "applied_call_indexes_json")
