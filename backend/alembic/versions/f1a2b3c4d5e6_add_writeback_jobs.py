"""add_writeback_jobs

Revision ID: f1a2b3c4d5e6
Revises: e3b7c2d9a541
Create Date: 2026-02-10 19:10:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f1a2b3c4d5e6"
down_revision = "e3b7c2d9a541"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "writeback_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("dry_run", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("docs_selected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("docs_changed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("calls_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("doc_ids_json", sa.Text(), nullable=True),
        sa.Column("calls_json", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(length=64), nullable=True),
        sa.Column("started_at", sa.String(length=64), nullable=True),
        sa.Column("finished_at", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_writeback_jobs_id", "writeback_jobs", ["id"])


def downgrade() -> None:
    op.drop_index("ix_writeback_jobs_id", table_name="writeback_jobs")
    op.drop_table("writeback_jobs")

