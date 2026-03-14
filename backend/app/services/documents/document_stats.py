from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import and_, case, exists, func, or_, select

from app.models import Document, DocumentEmbedding, DocumentPageText, DocumentSuggestion

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def compute_document_stats(db: Session) -> dict[str, int]:
    active_document = or_(
        Document.deleted_at.is_(None),
        ~Document.deleted_at.like("DELETED in Paperless%"),
    )
    embedding_exists = exists().where(DocumentEmbedding.doc_id == Document.id)
    vision_exists = exists().where(
        and_(DocumentPageText.doc_id == Document.id, DocumentPageText.source == "vision_ocr")
    )
    suggestion_exists = exists().where(DocumentSuggestion.doc_id == Document.id)
    fully_processed_exists = and_(embedding_exists, vision_exists, suggestion_exists)

    stmt = select(
        func.count(Document.id).label("total"),
        func.sum(case((embedding_exists, 1), else_=0)).label("embeddings"),
        func.sum(case((vision_exists, 1), else_=0)).label("vision"),
        func.sum(case((suggestion_exists, 1), else_=0)).label("suggestions"),
        func.sum(case((fully_processed_exists, 1), else_=0)).label("fully_processed"),
    ).where(active_document)
    row = db.execute(stmt).one()
    total = int(row.total or 0)
    embeddings = int(row.embeddings or 0)
    vision = int(row.vision or 0)
    suggestions = int(row.suggestions or 0)
    fully_processed = int(row.fully_processed or 0)
    return {
        "total": total,
        "processed": embeddings,
        "unprocessed": max(0, total - fully_processed),
        "embeddings": embeddings,
        "vision": vision,
        "suggestions": suggestions,
        "fully_processed": fully_processed,
    }
