from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import delete
from sqlalchemy.orm import Session
import logging

from app.models import DocumentPageText
from app.services.page_types import PageText
from app.services.text_pages import score_text_quality
from app.config import Settings
from app.services.text_cleaning import clean_ocr_text, estimate_tokens

logger = logging.getLogger(__name__)


def upsert_page_texts(
    db: Session,
    settings: Settings,
    doc_id: int,
    pages: list[PageText],
    source_filter: str | None = None,
    replace_pages: list[int] | None = None,
) -> None:
    if not pages:
        return
    sources = {page.source for page in pages}
    if source_filter:
        sources = {source_filter}
    delete_query = delete(DocumentPageText).where(
        DocumentPageText.doc_id == doc_id,
        DocumentPageText.source.in_(sources),
    )
    if replace_pages:
        page_set = sorted({int(page) for page in replace_pages if int(page) > 0})
        if page_set:
            delete_query = delete_query.where(DocumentPageText.page.in_(page_set))
    db.execute(delete_query)
    processed_at = datetime.now(timezone.utc).isoformat()
    created_at = processed_at
    for page in pages:
        if source_filter and page.source != source_filter:
            continue
        raw_text = page.text or ""
        clean_text = clean_ocr_text(raw_text)
        quality = score_text_quality(clean_text or raw_text, settings)
        db.add(
            DocumentPageText(
                doc_id=doc_id,
                page=page.page,
                source=page.source,
                text=raw_text,
                raw_text=raw_text,
                clean_text=clean_text,
                token_estimate_raw=estimate_tokens(raw_text),
                token_estimate_clean=estimate_tokens(clean_text),
                cleaned_at=processed_at,
                quality_score=quality.score,
                created_at=created_at,
                model_name=settings.vision_model,
                processed_at=processed_at,
            )
        )
    db.commit()
    logger.info("Stored page texts doc=%s sources=%s pages=%s", doc_id, sorted(sources), len(pages))
