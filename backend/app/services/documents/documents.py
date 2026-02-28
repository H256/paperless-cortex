from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Document
from app.services.integrations import paperless


def fetch_pdf_bytes(settings: Settings, doc_id: int) -> bytes:
    return paperless.get_document_pdf(settings, doc_id)


def fetch_pdf_bytes_for_doc(settings: Settings, doc: Document) -> bytes:
    return fetch_pdf_bytes(settings, doc.id)


def get_document_or_none(db: Session, doc_id: int) -> Document | None:
    return db.get(Document, doc_id)
