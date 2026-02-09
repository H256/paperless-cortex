from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import delete
from sqlalchemy.orm import Session
import logging

from app.models import DocumentPageText
from app.services.page_types import PageText
from app.services.text_pages import score_text_quality
from app.config import Settings

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
        quality = score_text_quality(page.text, settings)
        db.add(
            DocumentPageText(
                doc_id=doc_id,
                page=page.page,
                source=page.source,
                text=page.text,
                quality_score=quality.score,
                created_at=created_at,
                model_name=settings.vision_model,
                processed_at=processed_at,
            )
        )
    db.commit()
    logger.info("Stored page texts doc=%s sources=%s pages=%s", doc_id, sorted(sources), len(pages))
