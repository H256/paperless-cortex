"""add_task_run_composite_indexes

Revision ID: b7c4d8e9f1a2
Revises: fa11d0c9b2e1
Create Date: 2026-03-12 16:40:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "b7c4d8e9f1a2"
down_revision = "fa11d0c9b2e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_task_runs_doc_task_source_id",
        "task_runs",
        ["doc_id", "task", "source", "id"],
        unique=False,
    )
    op.create_index(
        "ix_task_runs_status_task_id",
        "task_runs",
        ["status", "task", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_task_runs_status_task_id", table_name="task_runs")
    op.drop_index("ix_task_runs_doc_task_source_id", table_name="task_runs")
