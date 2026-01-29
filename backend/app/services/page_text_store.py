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
) -> None:
    if not pages:
        return
    sources = {page.source for page in pages}
    if source_filter:
        sources = {source_filter}
    db.execute(
        delete(DocumentPageText).where(
            DocumentPageText.doc_id == doc_id,
            DocumentPageText.source.in_(sources),
        )
    )
    created_at = datetime.now(timezone.utc).isoformat()
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
            )
        )
    db.commit()
    logger.info("Stored page texts doc=%s sources=%s pages=%s", doc_id, sorted(sources), len(pages))
