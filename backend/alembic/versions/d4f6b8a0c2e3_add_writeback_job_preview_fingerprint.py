"""add_writeback_job_preview_fingerprint

Revision ID: d4f6b8a0c2e3
Revises: c3e5a7b9d1f2
Create Date: 2026-11-27 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "d4f6b8a0c2e3"
down_revision = "c3e5a7b9d1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("writeback_jobs", sa.Column("preview_fingerprint_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("writeback_jobs", "preview_fingerprint_json")
