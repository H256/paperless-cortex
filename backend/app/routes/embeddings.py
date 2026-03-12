from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query

from app.api_models import (
    EmbeddingIngestResponse,
    EmbeddingSearchResponse,
    EmbeddingStatusResponse,
    SyncCancelResponse,
)
from app.db import get_db
from app.deps import get_settings
from app.models import Document
from app.services.documents.embedding_operations import (
    build_embedding_search_response,
    build_embedding_status_response,
    cancel_embeddings_ingest,
    enqueue_embedding_tasks,
    ingest_embeddings_for_documents,
)
from app.services.documents.page_texts_merge import collect_page_texts
from app.services.pipeline.queue import enqueue_task, queue_stats
from app.services.search.embedding_init import ensure_embedding_collection
from app.services.search.embeddings import (
    chunk_document_with_pages,
    delete_points_for_doc,
    embed_text,
    make_doc_point_id,
    make_point_id,
    search_points,
    upsert_points,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.config import Settings

router = APIRouter(prefix="/embeddings", tags=["embeddings"])
logger = logging.getLogger(__name__)


@router.post("/ingest", response_model=EmbeddingIngestResponse)
def ingest_embeddings(
    doc_id: int | None = Query(default=None),
    limit: int = Query(default=100),
    force: bool = Query(default=False),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    query = db.query(Document)
    if doc_id is not None:
        query = query.filter(Document.id == doc_id)
    documents = query.all() if limit <= 0 else query.limit(limit).all()
    if settings.queue_enabled:
        return enqueue_embedding_tasks(
            settings,
            db,
            documents,
            enqueue_task_fn=enqueue_task,
        )
    return ingest_embeddings_for_documents(
        db=db,
        settings=settings,
        documents=documents,
        force=force,
        ensure_embedding_collection_fn=ensure_embedding_collection,
        collect_page_texts_fn=collect_page_texts,
        chunk_document_with_pages_fn=chunk_document_with_pages,
        delete_points_for_doc_fn=delete_points_for_doc,
        embed_text_fn=embed_text,
        make_point_id_fn=make_point_id,
        make_doc_point_id_fn=make_doc_point_id,
        upsert_points_fn=upsert_points,
    )


@router.post("/ingest-docs", response_model=EmbeddingIngestResponse)
def ingest_documents(
    doc_ids: list[int],
    force: bool = Query(default=False),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    documents = db.query(Document).filter(Document.id.in_(doc_ids)).all()
    if settings.queue_enabled:
        return enqueue_embedding_tasks(
            settings,
            db,
            documents,
            enqueue_task_fn=enqueue_task,
        )
    return ingest_embeddings_for_documents(
        db=db,
        settings=settings,
        documents=documents,
        force=force,
        ensure_embedding_collection_fn=ensure_embedding_collection,
        collect_page_texts_fn=collect_page_texts,
        chunk_document_with_pages_fn=chunk_document_with_pages,
        delete_points_for_doc_fn=delete_points_for_doc,
        embed_text_fn=embed_text,
        make_point_id_fn=make_point_id,
        make_doc_point_id_fn=make_doc_point_id,
        upsert_points_fn=upsert_points,
    )


@router.get("/search", response_model=EmbeddingSearchResponse)
def search(
    q: str,
    top_k: int = 5,
    dedupe: bool = True,
    rerank: bool = True,
    source: str | None = None,
    min_quality: int | None = None,
    include_doc: bool = True,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return build_embedding_search_response(
        q=q,
        top_k=top_k,
        dedupe=dedupe,
        rerank=rerank,
        source=source,
        min_quality=min_quality,
        include_doc=include_doc,
        settings=settings,
        db=db,
        embed_text_fn=embed_text,
        search_points_fn=search_points,
    )


@router.get("/status", response_model=EmbeddingStatusResponse)
def embedding_status(
    db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> dict[str, object]:
    return build_embedding_status_response(db=db, settings=settings, queue_stats_fn=queue_stats)


@router.post("/cancel", response_model=SyncCancelResponse)
def cancel_embeddings(db: Session = Depends(get_db)) -> dict[str, object]:
    return cancel_embeddings_ingest(db)
