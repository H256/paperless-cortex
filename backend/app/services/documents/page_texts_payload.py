from __future__ import annotations

from typing import TYPE_CHECKING

from app.models import DocumentPageText
from app.services.documents.documents import fetch_pdf_bytes
from app.services.documents.text_pages import get_baseline_page_texts, score_text_quality
from app.services.integrations import paperless

if TYPE_CHECKING:
    import logging

    from sqlalchemy.orm import Session

    from app.config import Settings


def build_page_texts_payload(
    *,
    doc_id: int,
    settings: Settings,
    db: Session,
    logger: logging.Logger,
) -> dict[str, object]:
    raw = paperless.get_document_cached(settings, doc_id)
    content = raw.get("content")
    baseline_pages = get_baseline_page_texts(
        settings,
        content,
        fetch_pdf_bytes=lambda: fetch_pdf_bytes(settings, doc_id),
    )
    vision_pages = (
        db.query(DocumentPageText)
        .filter(DocumentPageText.doc_id == doc_id, DocumentPageText.source == "vision_ocr")
        .order_by(DocumentPageText.page.asc())
        .all()
    )
    pages: list[dict[str, object]] = []
    for page in baseline_pages:
        quality = score_text_quality(page.text, settings)
        pages.append(
            {
                "page": page.page,
                "source": page.source,
                "text": page.text,
                "quality": {
                    "score": quality.score,
                    "reasons": quality.reasons,
                    "metrics": quality.metrics,
                },
            }
        )
    for page in vision_pages:
        vision_text = (
            page.clean_text
            if isinstance(page.clean_text, str) and page.clean_text.strip()
            else page.text
        )
        pages.append(
            {
                "page": page.page,
                "source": page.source,
                "text": vision_text,
                "quality": {
                    "score": page.quality_score,
                    "reasons": [],
                    "metrics": {},
                },
            }
        )
    pages.sort(
        key=lambda current_page: (
            current_page.get("page") or 0,
            str(current_page.get("source") or ""),
        )
    )
    expected_pages_raw = raw.get("page_count")
    expected_pages = (
        int(expected_pages_raw)
        if isinstance(expected_pages_raw, int) and expected_pages_raw > 0
        else None
    )
    vision_page_numbers = {
        int(page.page)
        for page in vision_pages
        if getattr(page, "page", None) is not None and int(page.page) > 0
    }
    if expected_pages is not None:
        bounded_done = {page for page in vision_page_numbers if 1 <= page <= expected_pages}
        done_pages = len(bounded_done)
        missing_pages = max(0, expected_pages - done_pages)
        is_complete = done_pages >= expected_pages
        coverage_percent = (
            round((done_pages / expected_pages) * 100.0, 2) if expected_pages > 0 else None
        )
    else:
        done_pages = len(vision_page_numbers)
        missing_pages = None
        is_complete = False
        coverage_percent = None
    max_page = max(vision_page_numbers) if vision_page_numbers else None
    logger.info("Page texts doc=%s pages=%s", doc_id, len(pages))
    return {
        "doc_id": doc_id,
        "pages": pages,
        "vision_progress": {
            "expected_pages": expected_pages,
            "done_pages": done_pages,
            "missing_pages": missing_pages,
            "max_page": max_page,
            "is_complete": is_complete,
            "coverage_percent": coverage_percent,
        },
    }
