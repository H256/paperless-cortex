from __future__ import annotations

from typing import TYPE_CHECKING

from app.models import Document
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
