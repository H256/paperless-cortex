"""add_task_run_checkpoint

Revision ID: d4b8f3a1e77c
Revises: c9d3a7f1b214
Create Date: 2026-02-12 16:20:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "d4b8f3a1e77c"
down_revision = "c9d3a7f1b214"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("task_runs", sa.Column("checkpoint_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("task_runs", "checkpoint_json")
