"""add_suggestion_audit

Revision ID: 2f6e9b1a3c4d
Revises: 1c2b6e8f4d7a
Create Date: 2026-01-29 11:40:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2f6e9b1a3c4d'
down_revision = '1c2b6e8f4d7a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'suggestion_audit',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('doc_id', sa.Integer(), sa.ForeignKey('documents.id'), nullable=False),
        sa.Column('action', sa.String(length=64), nullable=False),
        sa.Column('source', sa.String(length=32), nullable=True),
        sa.Column('field', sa.String(length=32), nullable=True),
        sa.Column('old_value', sa.Text(), nullable=True),
        sa.Column('new_value', sa.Text(), nullable=True),
        sa.Column('created_at', sa.String(length=64), nullable=True),
    )
    op.create_index('ix_suggestion_audit_doc_id', 'suggestion_audit', ['doc_id'])


def downgrade() -> None:
    op.drop_index('ix_suggestion_audit_doc_id', table_name='suggestion_audit')
    op.drop_table('suggestion_audit')
