from __future__ import annotations

from typing import TYPE_CHECKING

from app.models import Document, DocumentPageText
from app.services.documents.documents import fetch_pdf_bytes_for_doc
from app.services.documents.page_text_store import upsert_page_texts
from app.services.documents.text_pages import get_baseline_page_texts, get_page_text_layers

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.config import Settings


def collect_page_texts(
    settings: Settings,
    db: Session,
    doc: Document,
    *,
    force_vision: bool = False,
) -> tuple[list, list, list]:
    baseline_pages = get_baseline_page_texts(
        settings,
        doc.content,
        fetch_pdf_bytes=lambda: fetch_pdf_bytes_for_doc(settings, doc),
    )
    vision_pages = (
        db.query(DocumentPageText)
        .filter(DocumentPageText.doc_id == doc.id, DocumentPageText.source == "vision_ocr")
        .order_by(DocumentPageText.page.asc())
        .all()
    )
    if force_vision:
        _, regenerated = get_page_text_layers(
            settings,
            doc.content,
            fetch_pdf_bytes=lambda: fetch_pdf_bytes_for_doc(settings, doc),
            force_full_vision=True,
        )
        if regenerated:
            upsert_page_texts(db, settings, doc.id, regenerated, source_filter="vision_ocr")
            vision_pages = regenerated
    page_texts = baseline_pages + vision_pages
    return baseline_pages, vision_pages, page_texts
