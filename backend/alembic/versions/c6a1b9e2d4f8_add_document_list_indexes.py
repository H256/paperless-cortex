"""add_document_list_indexes

Revision ID: c6a1b9e2d4f8
Revises: f5c3a9b2d1e4
Create Date: 2026-05-16 11:35:00.000000
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "c6a1b9e2d4f8"
down_revision = "f5c3a9b2d1e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_documents_correspondent_id", "documents", ["correspondent_id"])
    op.create_index("ix_documents_document_type_id", "documents", ["document_type_id"])
    op.create_index("ix_documents_deleted_at", "documents", ["deleted_at"])
    op.create_index("ix_documents_page_count", "documents", ["page_count"])
    op.create_index(
        "ix_document_tags_tag_id_document_id",
        "document_tags",
        ["tag_id", "document_id"],
    )
    op.create_index(
        "ix_document_page_texts_doc_id_source",
        "document_page_texts",
        ["doc_id", "source"],
    )
    op.create_index(
        "ix_suggestion_audit_doc_action_created",
        "suggestion_audit",
        ["doc_id", "action", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_suggestion_audit_doc_action_created", table_name="suggestion_audit")
    op.drop_index("ix_document_page_texts_doc_id_source", table_name="document_page_texts")
    op.drop_index("ix_document_tags_tag_id_document_id", table_name="document_tags")
    op.drop_index("ix_documents_page_count", table_name="documents")
    op.drop_index("ix_documents_deleted_at", table_name="documents")
    op.drop_index("ix_documents_document_type_id", table_name="documents")
    op.drop_index("ix_documents_correspondent_id", table_name="documents")
