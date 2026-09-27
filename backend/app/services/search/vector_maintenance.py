from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from app.models import DocumentEmbedding, TaskRun
from app.services.documents.dashboard_cache import invalidate_dashboard_cache
from app.services.documents.document_stats_cache import invalidate_document_stats_cache
from app.services.documents.documents_list_cache import invalidate_documents_list_cache
from app.services.documents.local_document_cache import invalidate_local_document_cache
from app.services.search.embeddings import (
    delete_all_chunk_points as _delete_all_chunk_points,
)
from app.services.search.embeddings import delete_points_for_doc as _delete_points_for_doc
from app.services.search.embeddings import (
    delete_similarity_points as _delete_similarity_points,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from logging import Logger

    from sqlalchemy.orm import Session

    from app.config import Settings


def delete_all_chunk_points(settings: Settings) -> None:
    _delete_all_chunk_points(settings)


def delete_points_for_doc(settings: Settings, doc_id: int) -> None:
    _delete_points_for_doc(settings, doc_id)


def delete_similarity_points(settings: Settings, *, doc_id: int | None = None) -> None:
    _delete_similarity_points(settings, doc_id=doc_id)


def delete_embeddings_payload(
    settings: Settings,
    db: Session,
    *,
    doc_id: int | None,
    logger: Logger,
    delete_points_for_doc_fn: Callable[[Settings, int], None] | None = None,
    delete_all_chunk_points_fn: Callable[[Settings], None] | None = None,
) -> dict[str, object]:
    delete_points = delete_points_for_doc_fn or delete_points_for_doc
    delete_all_points = delete_all_chunk_points_fn or delete_all_chunk_points
    if doc_id is not None:
        # Vector-store deletion is authoritative: only clear DB bookkeeping
        # once the vector points are confirmed deleted.
        try:
            delete_points(settings, doc_id)
        except (httpx.HTTPError, RuntimeError, ValueError) as exc:
            logger.warning("Failed to delete embedding points doc_id=%s: %s", doc_id, exc)
            return {"deleted": 0, "qdrant_deleted": 0, "qdrant_errors": 1}
        row = db.get(DocumentEmbedding, doc_id)
        if row:
            db.delete(row)
            db.commit()
            invalidate_dashboard_cache()
            invalidate_document_stats_cache()
            invalidate_documents_list_cache()
            invalidate_local_document_cache(doc_id)
        return {"deleted": 1, "qdrant_deleted": 1, "qdrant_errors": 0}

    try:
        delete_all_points(settings)
    except (httpx.HTTPError, RuntimeError, ValueError) as exc:
        logger.warning("Failed to delete all embedding points: %s", exc)
        return {"deleted": 0, "qdrant_deleted": 0, "qdrant_errors": 1}
    db.query(DocumentEmbedding).delete(synchronize_session=False)
    db.commit()
    invalidate_dashboard_cache()
    invalidate_document_stats_cache()
    invalidate_documents_list_cache()
    invalidate_local_document_cache()
    return {"deleted": 1, "qdrant_deleted": 1, "qdrant_errors": 0}


def delete_similarity_index_payload(
    settings: Settings,
    db: Session,
    *,
    doc_id: int | None,
    logger: Logger,
    delete_similarity_points_fn: Callable[..., None] | None = None,
) -> dict[str, object]:
    delete_similarity = delete_similarity_points_fn or delete_similarity_points
    # Vector-store deletion is authoritative: only clear TaskRun bookkeeping
    # once the vector points are confirmed deleted.
    try:
        delete_similarity(settings, doc_id=doc_id)
    except (httpx.HTTPError, RuntimeError, ValueError) as exc:
        logger.warning("Failed to delete similarity index points doc_id=%s: %s", doc_id, exc)
        return {"deleted": 0, "qdrant_deleted": 0, "qdrant_errors": 1}

    query = db.query(TaskRun).filter(TaskRun.task == "similarity_index")
    if doc_id is not None:
        query = query.filter(TaskRun.doc_id == int(doc_id))
    deleted = int(query.delete(synchronize_session=False) or 0)
    db.commit()
    invalidate_document_stats_cache()
    invalidate_documents_list_cache()
    invalidate_local_document_cache(doc_id)
    return {"deleted": deleted, "qdrant_deleted": 1, "qdrant_errors": 0}


def delete_document_chunk_vectors(
    settings: Settings,
    *,
    doc_id: int,
) -> None:
    delete_points_for_doc(settings, doc_id)
