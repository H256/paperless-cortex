"""add_task_runs_table

Revision ID: c9d3a7f1b214
Revises: aa91f0b6c2d1
Create Date: 2026-02-12 12:20:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "c9d3a7f1b214"
down_revision = "aa91f0b6c2d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "task_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("doc_id", sa.Integer(), nullable=True),
        sa.Column("task", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("worker_id", sa.String(length=128), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("error_type", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.String(length=64), nullable=True),
        sa.Column("finished_at", sa.String(length=64), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.String(length=64), nullable=True),
        sa.Column("updated_at", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_task_runs_id"), "task_runs", ["id"], unique=False)
    op.create_index(op.f("ix_task_runs_doc_id"), "task_runs", ["doc_id"], unique=False)
    op.create_index(op.f("ix_task_runs_task"), "task_runs", ["task"], unique=False)
    op.create_index(op.f("ix_task_runs_source"), "task_runs", ["source"], unique=False)
    op.create_index(op.f("ix_task_runs_status"), "task_runs", ["status"], unique=False)
    op.create_index(op.f("ix_task_runs_error_type"), "task_runs", ["error_type"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_task_runs_error_type"), table_name="task_runs")
    op.drop_index(op.f("ix_task_runs_status"), table_name="task_runs")
    op.drop_index(op.f("ix_task_runs_source"), table_name="task_runs")
    op.drop_index(op.f("ix_task_runs_task"), table_name="task_runs")
    op.drop_index(op.f("ix_task_runs_doc_id"), table_name="task_runs")
    op.drop_index(op.f("ix_task_runs_id"), table_name="task_runs")
    op.drop_table("task_runs")
