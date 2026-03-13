from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from app.models import DocumentEmbedding, TaskRun
from app.services.documents.dashboard_cache import invalidate_dashboard_cache
from app.services.documents.document_stats_cache import invalidate_document_stats_cache
from app.services.documents.documents_list_cache import invalidate_documents_list_cache
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
    qdrant_deleted = 0
    qdrant_errors = 0
    if doc_id is not None:
        try:
            delete_points(settings, doc_id)
            qdrant_deleted = 1
        except (httpx.HTTPError, RuntimeError, ValueError) as exc:
            qdrant_errors = 1
            logger.warning("Failed to delete embedding points doc_id=%s: %s", doc_id, exc)
        row = db.get(DocumentEmbedding, doc_id)
        if row:
            db.delete(row)
            db.commit()
            invalidate_dashboard_cache()
            invalidate_document_stats_cache()
            invalidate_documents_list_cache()
        return {"deleted": 1, "qdrant_deleted": qdrant_deleted, "qdrant_errors": qdrant_errors}

    db.query(DocumentEmbedding).delete(synchronize_session=False)
    db.commit()
    invalidate_dashboard_cache()
    invalidate_document_stats_cache()
    invalidate_documents_list_cache()
    try:
        delete_all_points(settings)
        qdrant_deleted = 1
    except (httpx.HTTPError, RuntimeError, ValueError) as exc:
        qdrant_errors = 1
        logger.warning("Failed to delete all embedding points: %s", exc)
    return {"deleted": 1, "qdrant_deleted": qdrant_deleted, "qdrant_errors": qdrant_errors}


def delete_similarity_index_payload(
    settings: Settings,
    db: Session,
    *,
    doc_id: int | None,
    logger: Logger,
    delete_similarity_points_fn: Callable[..., None] | None = None,
) -> dict[str, object]:
    delete_similarity = delete_similarity_points_fn or delete_similarity_points
    qdrant_deleted = 0
    qdrant_errors = 0
    try:
        delete_similarity(settings, doc_id=doc_id)
        qdrant_deleted = 1
    except (httpx.HTTPError, RuntimeError, ValueError) as exc:
        qdrant_errors = 1
        logger.warning("Failed to delete similarity index points doc_id=%s: %s", doc_id, exc)

    query = db.query(TaskRun).filter(TaskRun.task == "similarity_index")
    if doc_id is not None:
        query = query.filter(TaskRun.doc_id == int(doc_id))
    deleted = int(query.delete(synchronize_session=False) or 0)
    db.commit()
    invalidate_document_stats_cache()
    invalidate_documents_list_cache()
    return {"deleted": deleted, "qdrant_deleted": qdrant_deleted, "qdrant_errors": qdrant_errors}


def delete_document_chunk_vectors(
    settings: Settings,
    *,
    doc_id: int,
) -> None:
    delete_points_for_doc(settings, doc_id)
