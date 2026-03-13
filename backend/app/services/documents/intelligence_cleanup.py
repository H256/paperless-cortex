from __future__ import annotations

from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def clear_all_intelligence(db: Session) -> None:
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


def clear_document_intelligence(db: Session, doc_id: int) -> None:
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
