from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, case, exists, func, or_, select

from app.models import Document, DocumentEmbedding, DocumentPageText, DocumentSuggestion

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# Single source of the "active document" prefix literal (was duplicated verbatim
# across dashboard.py and document_stats.py).
DELETED_IN_PAPERLESS_PREFIX = "DELETED in Paperless%"


def active_document_filter() -> Any:
    """The 'active document' predicate: not deleted in Paperless."""
    return or_(
        Document.deleted_at.is_(None),
        ~Document.deleted_at.like(DELETED_IN_PAPERLESS_PREFIX),
    )


def coverage_exprs(require_vision: bool = True) -> tuple[Any, Any, Any, Any]:
    """Shared coverage subqueries.

    Returns (embedding_exists, vision_exists, suggestion_exists, is_processed)
    where is_processed = and_(embedding, vision, suggestion).
    """
    embedding_exists = exists().where(DocumentEmbedding.doc_id == Document.id)
    vision_exists = exists().where(
        and_(DocumentPageText.doc_id == Document.id, DocumentPageText.source == "vision_ocr")
    )
    suggestion_exists = exists().where(DocumentSuggestion.doc_id == Document.id)
    if require_vision:
        is_processed = and_(embedding_exists, vision_exists, suggestion_exists)
    else:
        is_processed = and_(embedding_exists, suggestion_exists)
    return embedding_exists, vision_exists, suggestion_exists, is_processed


def build_stats_dict(
    total: int,
    embeddings: int,
    vision: int,
    suggestions: int,
    fully_processed: int,
) -> dict[str, int]:
    """Build the 7-key active-document stats dict (single source of shape)."""
    return {
        "total": total,
        "processed": embeddings,
        "unprocessed": max(0, total - fully_processed),
        "embeddings": embeddings,
        "vision": vision,
        "suggestions": suggestions,
        "fully_processed": fully_processed,
    }


def active_document_stats(db: Session, require_vision: bool = True) -> dict[str, int]:
    """Compute the 7-key active-document stats dict (single source of shape)."""
    embedding_exists, vision_exists, suggestion_exists, is_processed = coverage_exprs(require_vision)
    stmt = select(
        func.count(Document.id).label("total"),
        func.sum(case((embedding_exists, 1), else_=0)).label("embeddings"),
        func.sum(case((vision_exists, 1), else_=0)).label("vision"),
        func.sum(case((suggestion_exists, 1), else_=0)).label("suggestions"),
        func.sum(case((is_processed, 1), else_=0)).label("fully_processed"),
    ).where(active_document_filter())
    row = db.execute(stmt).one()
    return build_stats_dict(
        int(row.total or 0),
        int(row.embeddings or 0),
        int(row.vision or 0),
        int(row.suggestions or 0),
        int(row.fully_processed or 0),
    )
