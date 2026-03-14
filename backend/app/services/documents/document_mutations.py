from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from app.models import DocumentOcrScore, DocumentPageText, DocumentSuggestion

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

InvalidateAll = Callable[[], None]
InvalidateDoc = Callable[[int | None], None]


def delete_vision_ocr_payload(
    *,
    db: Session,
    doc_id: int | None,
    invalidate_dashboard_cache_fn: InvalidateAll,
    invalidate_document_stats_cache_fn: InvalidateAll,
    invalidate_documents_list_cache_fn: InvalidateAll,
    invalidate_local_document_cache_fn: InvalidateDoc,
    invalidate_page_texts_cache_fn: InvalidateDoc,
) -> dict[str, object]:
    query = db.query(DocumentPageText).filter(DocumentPageText.source == "vision_ocr")
    if doc_id is not None:
        query = query.filter(DocumentPageText.doc_id == doc_id)
    count = int(query.delete(synchronize_session=False) or 0)

    score_query = db.query(DocumentOcrScore).filter(DocumentOcrScore.source == "vision_ocr")
    if doc_id is not None:
        score_query = score_query.filter(DocumentOcrScore.doc_id == doc_id)
    score_query.delete(synchronize_session=False)

    db.commit()
    invalidate_dashboard_cache_fn()
    invalidate_document_stats_cache_fn()
    invalidate_documents_list_cache_fn()
    invalidate_local_document_cache_fn(doc_id)
    invalidate_page_texts_cache_fn(doc_id)
    return {"deleted": count}


def delete_suggestions_payload(
    *,
    db: Session,
    doc_id: int | None,
    invalidate_dashboard_cache_fn: InvalidateAll,
    invalidate_document_stats_cache_fn: InvalidateAll,
    invalidate_documents_list_cache_fn: InvalidateAll,
    invalidate_local_document_cache_fn: InvalidateDoc,
) -> dict[str, object]:
    query = db.query(DocumentSuggestion)
    if doc_id is not None:
        query = query.filter(DocumentSuggestion.doc_id == doc_id)
    count = int(query.delete(synchronize_session=False) or 0)

    db.commit()
    invalidate_dashboard_cache_fn()
    invalidate_document_stats_cache_fn()
    invalidate_documents_list_cache_fn()
    invalidate_local_document_cache_fn(doc_id)
    return {"deleted": count}
