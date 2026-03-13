from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.orm import load_only, selectinload

from app.models import Correspondent, Document, DocumentNote, DocumentType, Tag
from app.services.integrations import paperless

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.config import Settings


def fetch_pdf_bytes(settings: Settings, doc_id: int) -> bytes:
    """Fetch PDF file bytes from Paperless-NGX for a document.

    Args:
        settings: Application settings with Paperless configuration
        doc_id: Document ID in Paperless

    Returns:
        Raw PDF file bytes

    Raises:
        HTTPError: If document not found or API error occurs
    """
    return paperless.get_document_pdf(settings, doc_id)


def fetch_pdf_bytes_for_doc(settings: Settings, doc: Document) -> bytes:
    """Fetch PDF bytes for a Document ORM instance.

    Convenience wrapper around fetch_pdf_bytes that accepts a Document object.

    Args:
        settings: Application settings
        doc: Document ORM instance

    Returns:
        Raw PDF file bytes
    """
    return fetch_pdf_bytes(settings, doc.id)


def get_document_or_none(db: Session, doc_id: int) -> Document | None:
    """Retrieve a document by ID from the database.

    Args:
        db: SQLAlchemy database session
        doc_id: Document primary key

    Returns:
        Document instance if found, None otherwise

    Example:
        >>> doc = get_document_or_none(db, 123)
        >>> if doc:
        ...     print(doc.title)
    """
    return db.get(Document, doc_id)


def get_document_detail_or_none(db: Session, doc_id: int) -> Document | None:
    """Retrieve a document with the local-detail relationships eagerly loaded.

    This is the optimized read path for `/documents/{id}/local`, where the
    response needs tags, notes, correspondent, and document type in addition to
    the base document row.
    """
    return (
        db.query(Document)
        .options(
            load_only(
                Document.id,
                Document.title,
                Document.content,
                Document.document_date,
                Document.created,
                Document.modified,
                Document.correspondent_id,
                Document.document_type_id,
                Document.original_file_name,
                Document.page_count,
            ),
            selectinload(Document.tags).load_only(Tag.id),
            selectinload(Document.notes).load_only(DocumentNote.id, DocumentNote.note),
            selectinload(Document.correspondent).load_only(Correspondent.id, Correspondent.name),
            selectinload(Document.document_type).load_only(DocumentType.id, DocumentType.name),
        )
        .filter(Document.id == int(doc_id))
        .one_or_none()
    )
