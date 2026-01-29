"""add_document_page_texts

Revision ID: 8d2a6a9f2a1b
Revises: 734a3748aa6a
Create Date: 2026-01-29 10:15:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8d2a6a9f2a1b'
down_revision = '734a3748aa6a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'document_page_texts',
        sa.Column('doc_id', sa.Integer(), sa.ForeignKey('documents.id'), primary_key=True),
        sa.Column('page', sa.Integer(), primary_key=True),
        sa.Column('source', sa.String(length=32), primary_key=True),
        sa.Column('text', sa.Text(), nullable=True),
        sa.Column('quality_score', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('document_page_texts')
