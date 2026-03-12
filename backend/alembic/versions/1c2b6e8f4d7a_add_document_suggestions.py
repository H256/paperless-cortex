"""add_document_suggestions

Revision ID: 1c2b6e8f4d7a
Revises: 8d2a6a9f2a1b
Create Date: 2026-01-29 11:05:00.000000
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = '1c2b6e8f4d7a'
down_revision = '8d2a6a9f2a1b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'document_suggestions',
        sa.Column('doc_id', sa.Integer(), sa.ForeignKey('documents.id'), primary_key=True),
        sa.Column('source', sa.String(length=32), primary_key=True),
        sa.Column('payload', sa.Text(), nullable=False),
        sa.Column('created_at', sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('document_suggestions')
