from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING

import httpx
from sqlalchemy import delete

from app.models import (
    DocumentEmbedding,
    DocumentOcrScore,
    DocumentPageAnchor,
    DocumentPageNote,
    DocumentPageText,
    DocumentSectionSummary,
    DocumentSuggestion,
    TaskRun,
)
from app.services.documents.dashboard_cache import invalidate_dashboard_cache
from app.services.documents.document_stats_cache import invalidate_document_stats_cache
from app.services.documents.documents_list_cache import invalidate_documents_list_cache
from app.services.documents.local_document_cache import invalidate_local_document_cache
from app.services.documents.page_texts_cache import invalidate_page_texts_cache
from app.services.search.embeddings import delete_all_chunk_points, delete_points_for_doc

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.config import Settings


def clear_all_intelligence(db: Session, settings: Settings | None = None) -> None:
    db.execute(delete(DocumentSuggestion))
    db.execute(delete(DocumentPageText))
    db.execute(delete(DocumentEmbedding))
    db.execute(delete(DocumentOcrScore))
    db.execute(delete(DocumentPageNote))
    db.execute(delete(DocumentSectionSummary))
    db.execute(delete(DocumentPageAnchor))
    db.commit()
    invalidate_dashboard_cache()
    invalidate_document_stats_cache()
    invalidate_documents_list_cache()
    invalidate_local_document_cache()
    invalidate_page_texts_cache()
    if settings is not None:
        with suppress(httpx.HTTPError, RuntimeError, ValueError):
            delete_all_chunk_points(settings)


def clear_document_intelligence(
    db: Session, doc_id: int, settings: Settings | None = None
) -> None:
    db.query(DocumentSuggestion).filter(DocumentSuggestion.doc_id == doc_id).delete(
        synchronize_session=False
    )
    db.query(DocumentPageText).filter(DocumentPageText.doc_id == doc_id).delete(
        synchronize_session=False
    )
    db.query(DocumentEmbedding).filter(DocumentEmbedding.doc_id == doc_id).delete(
        synchronize_session=False
    )
    db.query(DocumentOcrScore).filter(DocumentOcrScore.doc_id == doc_id).delete(
        synchronize_session=False
    )
    db.query(DocumentPageNote).filter(DocumentPageNote.doc_id == doc_id).delete(
        synchronize_session=False
    )
    db.query(DocumentSectionSummary).filter(DocumentSectionSummary.doc_id == doc_id).delete(
        synchronize_session=False
    )
    db.query(DocumentPageAnchor).filter(DocumentPageAnchor.doc_id == doc_id).delete(
        synchronize_session=False
    )
    db.query(TaskRun).filter(TaskRun.doc_id == doc_id).delete(synchronize_session=False)
    db.commit()
    invalidate_dashboard_cache()
    invalidate_document_stats_cache()
    invalidate_documents_list_cache()
    invalidate_local_document_cache(doc_id)
    invalidate_page_texts_cache(doc_id)
    if settings is not None:
        with suppress(httpx.HTTPError, RuntimeError, ValueError):
            delete_points_for_doc(settings, doc_id)
