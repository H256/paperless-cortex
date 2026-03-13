from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from app.api_models import (
    SyncCancelResponse,
    SyncDocumentResponse,
    SyncDocumentsResponse,
    SyncSimpleResponse,
    SyncStatusResponse,
)
from app.db import get_db
from app.deps import get_settings
from app.services.documents.dashboard_cache import invalidate_dashboard_cache
from app.services.documents.document_stats_cache import invalidate_document_stats_cache
from app.services.documents.documents_list_cache import invalidate_documents_list_cache
from app.services.documents.sync_operations import (
    build_sync_status_payload,
    cancel_documents_sync,
    embed_documents,
    merge_document_notes,
    run_documents_sync,
    run_single_document_sync,
    upsert_document,
)
from app.services.integrations import paperless
from app.services.integrations.meta_sync import (
    sync_correspondents_page,
    sync_document_types_page,
    sync_tags_page,
)
from app.services.pipeline.queue import enqueue_task_sequence, enqueue_task_sequence_front
from app.services.pipeline.queue_tasks import build_task_sequence

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.config import Settings

router = APIRouter(prefix="/sync", tags=["sync"])
logger = logging.getLogger(__name__)
ResponseDict = dict[str, object]
_merge_document_notes = merge_document_notes
_upsert_document = upsert_document
_embed_documents = embed_documents


@router.post("/documents", response_model=SyncDocumentsResponse)
def sync_documents(
    page_size: int = 50,
    incremental: bool = True,
    embed: bool | None = None,
    page: int = 1,
    page_only: bool = False,
    force_embed: bool = False,
    mark_missing: bool = False,
    insert_only: bool = False,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> ResponseDict:
    """Synchronize Paperless documents into the local cache and optionally queue embeddings."""
    if embed is None:
        embed = settings.embed_on_sync
    payload = run_documents_sync(
        db=db,
        settings=settings,
        page_size=page_size,
        incremental=incremental,
        embed=embed,
        page=page,
        page_only=page_only,
        force_embed=force_embed,
        mark_missing=mark_missing,
        insert_only=insert_only,
        list_documents_fn=paperless.list_documents,
        build_task_sequence_fn=build_task_sequence,
        enqueue_task_sequence_fn=enqueue_task_sequence,
    )
    invalidate_dashboard_cache()
    invalidate_document_stats_cache()
    invalidate_documents_list_cache()
    return payload


@router.get("/documents", response_model=SyncStatusResponse)
def sync_status(db: Session = Depends(get_db)) -> ResponseDict:
    """Return the current document-sync progress snapshot from local sync state."""
    return build_sync_status_payload(db)


@router.post("/documents/cancel", response_model=SyncCancelResponse)
def cancel_sync(db: Session = Depends(get_db)) -> ResponseDict:
    """Request cancellation of the running document-sync job, if any."""
    return cancel_documents_sync(db)


@router.post("/documents/{doc_id}", response_model=SyncDocumentResponse)
def sync_document(
    doc_id: int,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
    embed: bool | None = None,
    force_embed: bool = False,
    priority: bool = False,
) -> ResponseDict:
    """Refresh one Paperless document locally and optionally enqueue or run embeddings."""
    if embed is None:
        embed = settings.embed_on_sync
    payload = run_single_document_sync(
        doc_id=doc_id,
        db=db,
        settings=settings,
        embed=embed,
        force_embed=force_embed,
        priority=priority,
        get_document_fn=paperless.get_document,
        build_task_sequence_fn=build_task_sequence,
        enqueue_task_sequence_fn=enqueue_task_sequence,
        enqueue_task_sequence_front_fn=lambda active_settings, tasks: enqueue_task_sequence_front(
            active_settings, tasks, force=True
        ),
    )
    invalidate_dashboard_cache()
    invalidate_document_stats_cache()
    invalidate_documents_list_cache()
    return payload


@router.post("/tags", response_model=SyncSimpleResponse)
def sync_tags(
    page: int = 1,
    page_size: int = 200,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> ResponseDict:
    """Upsert one page of Paperless tags into the local metadata cache."""
    count, upserted = sync_tags_page(settings, db, page=page, page_size=page_size)
    return {"count": count, "upserted": upserted}


@router.post("/correspondents", response_model=SyncSimpleResponse)
def sync_correspondents(
    page: int = 1,
    page_size: int = 200,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> ResponseDict:
    """Upsert one page of Paperless correspondents into the local metadata cache."""
    count, upserted = sync_correspondents_page(settings, db, page=page, page_size=page_size)
    return {"count": count, "upserted": upserted}


@router.post("/document-types", response_model=SyncSimpleResponse)
def sync_document_types(
    page: int = 1,
    page_size: int = 200,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> ResponseDict:
    """Upsert one page of Paperless document types into the local metadata cache."""
    count, upserted = sync_document_types_page(settings, db, page=page, page_size=page_size)
    return {"count": count, "upserted": upserted}

