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


def reclean_page_texts(
    db: Session,
    settings: Settings,
    *,
    doc_id: int | None = None,
    source: str | None = None,
    clear_first: bool = False,
) -> dict[str, int]:
    query = db.query(DocumentPageText)
    if doc_id is not None:
        query = query.filter(DocumentPageText.doc_id == int(doc_id))
    if source:
        query = query.filter(DocumentPageText.source == source)
    rows = query.all()
    if not rows:
        return {"processed": 0, "updated": 0}
    now = datetime.now(timezone.utc).isoformat()
    processed = 0
    updated = 0
    for row in rows:
        processed += 1
        if clear_first:
            row.clean_text = None
            row.token_estimate_clean = None
            row.cleaned_at = None
        raw_text = row.raw_text if row.raw_text is not None else (row.text or "")
        clean_text = clean_ocr_text(raw_text)
        token_raw = estimate_tokens(raw_text)
        token_clean = estimate_tokens(clean_text)
        quality = score_text_quality(clean_text or raw_text, settings)
        changed = (
            row.raw_text != raw_text
            or row.clean_text != clean_text
            or row.token_estimate_raw != token_raw
            or row.token_estimate_clean != token_clean
            or row.quality_score != quality.score
        )
        row.raw_text = raw_text
        row.text = raw_text
        row.clean_text = clean_text
        row.token_estimate_raw = token_raw
        row.token_estimate_clean = token_clean
        row.quality_score = quality.score
        row.cleaned_at = now
        row.processed_at = now
        if changed:
            updated += 1
    db.commit()
    logger.info(
        "Re-cleaned page texts doc_id=%s source=%s clear_first=%s processed=%s updated=%s",
        doc_id,
        source or "all",
        clear_first,
        processed,
        updated,
    )
    return {"processed": processed, "updated": updated}
