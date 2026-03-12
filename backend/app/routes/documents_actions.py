from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ValidationError
from sqlalchemy import delete
from sqlalchemy.exc import SQLAlchemyError

from app.api_models import (
    CleanupTextsResponse,
    ClearIntelligenceResponse,
    DeleteEmbeddingsResponse,
    DeleteSimilarityIndexResponse,
    DeleteSuggestionsResponse,
    DeleteVisionOcrResponse,
    DocumentIn,
    DocumentOperationEnqueueResponse,
    DocumentPipelineContinueResponse,
    DocumentPipelineFanoutResponse,
    DocumentPipelineStatusResponse,
    DocumentResetReprocessResponse,
    ProcessMissingResponse,
    ResetIntelligenceResponse,
)
from app.db import get_db
from app.deps import get_settings
from app.exceptions import DocumentNotFoundError
from app.models import (
    Document,
    DocumentEmbedding,
    DocumentOcrScore,
    DocumentPageAnchor,
    DocumentPageNote,
    DocumentPageText,
    DocumentSectionSummary,
    DocumentSuggestion,
    TaskRun,
)
from app.routes.queue_guard import require_queue_enabled
from app.services.documents.dashboard_cache import invalidate_dashboard_cache
from app.services.documents.operations import (
    build_document_pipeline_fanout_payload,
    build_document_pipeline_status_payload,
    build_pipeline_options,
    continue_document_pipeline_payload,
    run_cleanup_texts,
)
from app.services.documents.sync_operations import run_documents_sync, upsert_document
from app.services.integrations import paperless
from app.services.pipeline.process_missing import ProcessMissingOptions, process_missing_documents
from app.services.pipeline.queue import (
    enqueue_task,
    enqueue_task_sequence,
    enqueue_task_sequence_front,
)
from app.services.pipeline.queue_tasks import build_task_sequence
from app.services.search.embeddings import delete_points_for_doc, delete_similarity_points

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.config import Settings

router = APIRouter(prefix="/documents", tags=["documents"])
logger = logging.getLogger(__name__)
ResponseDict = dict[str, object]
ReferenceCache = dict[str, set[int]]

ALLOWED_DOC_TASKS = {
    "sync",
    "evidence_index",
    "vision_ocr",
    "cleanup_texts",
    "embeddings_paperless",
    "embeddings_vision",
    "similarity_index",
    "page_notes_paperless",
    "page_notes_vision",
    "summary_hierarchical",
    "suggestions_paperless",
    "suggestions_vision",
}


def _run_documents_sync_for_process_missing(
    *,
    page_size: int = 50,
    incremental: bool = True,
    embed: bool | None = None,
    page: int = 1,
    page_only: bool = False,
    force_embed: bool = False,
    mark_missing: bool = False,
    insert_only: bool = False,
    settings: Settings,
    db: Session,
) -> ResponseDict:
    if embed is None:
        embed = settings.embed_on_sync
    return run_documents_sync(
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


def _get_or_sync_local_document(
    *,
    db: Session,
    settings: Settings,
    doc_id: int,
) -> Document:
    doc = db.get(Document, int(doc_id))
    if doc:
        return doc
    try:
        raw = paperless.get_document(settings, int(doc_id))
        data = DocumentIn.model_validate(raw)
        cache: ReferenceCache = {"correspondents": set(), "document_types": set(), "tags": set()}
        upsert_document(db, settings, data, cache)
        db.commit()
        doc = db.get(Document, int(doc_id))
        if doc:
            logger.info("Auto-synced missing local document doc_id=%s", doc_id)
            return doc
    except (httpx.HTTPError, RuntimeError, ValidationError, SQLAlchemyError, ValueError):
        logger.warning(
            "Failed to auto-sync missing local document doc_id=%s", doc_id, exc_info=True
        )
    raise DocumentNotFoundError(int(doc_id))


class DocumentTaskRequest(BaseModel):
    task: str
    source: str | None = None
    force: bool = False
    clear_first: bool = False


class CleanupTextsRequest(BaseModel):
    doc_ids: list[int] | None = None
    source: str | None = None
    clear_first: bool = False
    enqueue: bool = True


def _clear_intelligence_tables(db: Session) -> None:
    db.execute(delete(DocumentSuggestion))
    db.execute(delete(DocumentPageText))
    db.execute(delete(DocumentEmbedding))
    db.execute(delete(DocumentOcrScore))
    db.execute(delete(DocumentPageNote))
    db.execute(delete(DocumentSectionSummary))
    db.execute(delete(DocumentPageAnchor))
    db.commit()
    invalidate_dashboard_cache()


def _clear_doc_intelligence(db: Session, doc_id: int) -> None:
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
    # Reset should not keep stale per-doc pipeline history; it confuses fan-out/status views.
    db.query(TaskRun).filter(TaskRun.doc_id == doc_id).delete(synchronize_session=False)
    db.commit()
    invalidate_dashboard_cache()


@router.post("/process-missing", response_model=ProcessMissingResponse)
def process_missing(
    dry_run: bool = False,
    include_sync: bool = True,
    include_evidence_index: bool = True,
    include_vision_ocr: bool = True,
    include_embeddings: bool = True,
    include_embeddings_paperless: bool = True,
    include_embeddings_vision: bool = True,
    include_doc_similarity_index: bool = True,
    include_page_notes: bool = True,
    include_summary_hierarchical: bool = True,
    include_suggestions_paperless: bool = True,
    include_suggestions_vision: bool = True,
    embeddings_mode: str = "auto",
    limit: int | None = None,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> ResponseDict:
    if not require_queue_enabled(settings):
        return {"enabled": False, "docs": 0, "enqueued": 0, "tasks": 0, "dry_run": dry_run}
    if embeddings_mode not in ("auto", "paperless", "vision", "both"):
        raise HTTPException(status_code=400, detail="Invalid embeddings_mode")
    if limit is not None and limit < 1:
        raise HTTPException(status_code=400, detail="limit must be >= 1")
    options = ProcessMissingOptions(
        dry_run=dry_run,
        include_sync=include_sync,
        include_evidence_index=include_evidence_index,
        include_vision_ocr=include_vision_ocr,
        include_embeddings=include_embeddings,
        include_embeddings_paperless=include_embeddings_paperless,
        include_embeddings_vision=include_embeddings_vision,
        include_doc_similarity_index=include_doc_similarity_index,
        include_page_notes=include_page_notes,
        include_summary_hierarchical=include_summary_hierarchical,
        include_suggestions_paperless=include_suggestions_paperless,
        include_suggestions_vision=include_suggestions_vision,
        embeddings_mode=embeddings_mode,
        limit=limit,
    )
    return process_missing_documents(
        settings=settings,
        db=db,
        options=options,
        run_sync_documents=_run_documents_sync_for_process_missing,
        enqueue_task_sequence=enqueue_task_sequence,
    )


@router.get("/{doc_id}/pipeline-status", response_model=DocumentPipelineStatusResponse)
def get_document_pipeline_status(
    doc_id: int,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> ResponseDict:
    try:
        doc = _get_or_sync_local_document(db=db, settings=settings, doc_id=int(doc_id))
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc
    return build_document_pipeline_status_payload(
        doc_id=int(doc_id),
        doc=doc,
        settings=settings,
        db=db,
    )


@router.get("/{doc_id}/pipeline-fanout", response_model=DocumentPipelineFanoutResponse)
def get_document_pipeline_fanout(
    doc_id: int,
    include_sync: bool = True,
    include_evidence_index: bool = True,
    include_vision_ocr: bool = True,
    include_embeddings: bool = True,
    include_embeddings_paperless: bool = True,
    include_embeddings_vision: bool = True,
    include_doc_similarity_index: bool = True,
    include_page_notes: bool = True,
    include_summary_hierarchical: bool = True,
    include_suggestions_paperless: bool = True,
    include_suggestions_vision: bool = True,
    embeddings_mode: str = "auto",
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> ResponseDict:
    try:
        doc = _get_or_sync_local_document(db=db, settings=settings, doc_id=int(doc_id))
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc
    try:
        options = build_pipeline_options(
            include_sync=include_sync,
            include_evidence_index=include_evidence_index,
            include_vision_ocr=include_vision_ocr,
            include_embeddings=include_embeddings,
            include_embeddings_paperless=include_embeddings_paperless,
            include_embeddings_vision=include_embeddings_vision,
            include_doc_similarity_index=include_doc_similarity_index,
            include_page_notes=include_page_notes,
            include_summary_hierarchical=include_summary_hierarchical,
            include_suggestions_paperless=include_suggestions_paperless,
            include_suggestions_vision=include_suggestions_vision,
            embeddings_mode=embeddings_mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return build_document_pipeline_fanout_payload(
        doc_id=int(doc_id),
        doc=doc,
        settings=settings,
        db=db,
        options=options,
    )


@router.post("/{doc_id}/pipeline/continue", response_model=DocumentPipelineContinueResponse)
def continue_document_pipeline(
    doc_id: int,
    dry_run: bool = False,
    include_sync: bool = True,
    include_evidence_index: bool = True,
    include_vision_ocr: bool = True,
    include_embeddings: bool = True,
    include_embeddings_paperless: bool = True,
    include_embeddings_vision: bool = True,
    include_doc_similarity_index: bool = True,
    include_page_notes: bool = True,
    include_summary_hierarchical: bool = True,
    include_suggestions_paperless: bool = True,
    include_suggestions_vision: bool = True,
    embeddings_mode: str = "auto",
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> ResponseDict:
    try:
        doc = _get_or_sync_local_document(db=db, settings=settings, doc_id=int(doc_id))
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc
    try:
        options = build_pipeline_options(
            include_sync=include_sync,
            include_evidence_index=include_evidence_index,
            include_vision_ocr=include_vision_ocr,
            include_embeddings=include_embeddings,
            include_embeddings_paperless=include_embeddings_paperless,
            include_embeddings_vision=include_embeddings_vision,
            include_doc_similarity_index=include_doc_similarity_index,
            include_page_notes=include_page_notes,
            include_summary_hierarchical=include_summary_hierarchical,
            include_suggestions_paperless=include_suggestions_paperless,
            include_suggestions_vision=include_suggestions_vision,
            embeddings_mode=embeddings_mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return continue_document_pipeline_payload(
        doc_id=int(doc_id),
        doc=doc,
        settings=settings,
        db=db,
        options=options,
        dry_run=dry_run,
        queue_enabled=require_queue_enabled(settings),
        enqueue_task_sequence=enqueue_task_sequence,
    )


@router.post("/reset-intelligence", response_model=ResetIntelligenceResponse)
def reset_intelligence(
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> ResponseDict:
    if not require_queue_enabled(settings):
        return {"enabled": False}
    _clear_intelligence_tables(db)
    return {"enabled": True}


@router.post("/clear-intelligence", response_model=ClearIntelligenceResponse)
def clear_intelligence(
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> ResponseDict:
    if not require_queue_enabled(settings):
        return {"enabled": False}
    _clear_intelligence_tables(db)
    return {"enabled": True}


@router.post("/delete/vision-ocr", response_model=DeleteVisionOcrResponse)
def delete_vision_ocr(
    doc_id: int | None = None,
    db: Session = Depends(get_db),
) -> ResponseDict:
    query = db.query(DocumentPageText).filter(DocumentPageText.source == "vision_ocr")
    if doc_id is not None:
        query = query.filter(DocumentPageText.doc_id == doc_id)
    count = int(query.delete(synchronize_session=False) or 0)
    score_query = db.query(DocumentOcrScore).filter(DocumentOcrScore.source == "vision_ocr")
    if doc_id is not None:
        score_query = score_query.filter(DocumentOcrScore.doc_id == doc_id)
    score_query.delete(synchronize_session=False)
    db.commit()
    invalidate_dashboard_cache()
    return {"deleted": count}


@router.post("/delete/suggestions", response_model=DeleteSuggestionsResponse)
def delete_suggestions(
    doc_id: int | None = None,
    db: Session = Depends(get_db),
) -> ResponseDict:
    query = db.query(DocumentSuggestion)
    if doc_id is not None:
        query = query.filter(DocumentSuggestion.doc_id == doc_id)
    count = int(query.delete(synchronize_session=False) or 0)
    db.commit()
    invalidate_dashboard_cache()
    return {"deleted": count}


@router.post("/delete/embeddings", response_model=DeleteEmbeddingsResponse)
def delete_embeddings(
    doc_id: int | None = None,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> ResponseDict:
    if doc_id is not None:
        delete_points_for_doc(settings, doc_id)
        row = db.get(DocumentEmbedding, doc_id)
        if row:
            db.delete(row)
            db.commit()
            invalidate_dashboard_cache()
        return {"deleted": 1}
    db.query(DocumentEmbedding).delete(synchronize_session=False)
    db.commit()
    invalidate_dashboard_cache()
    return {"deleted": 1}


@router.post("/delete/similarity-index", response_model=DeleteSimilarityIndexResponse)
def delete_similarity_index(
    doc_id: int | None = None,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> ResponseDict:
    qdrant_deleted = 0
    qdrant_errors = 0
    try:
        delete_similarity_points(settings, doc_id=doc_id)
        qdrant_deleted = 1
    except (httpx.HTTPError, RuntimeError, ValueError) as exc:
        qdrant_errors = 1
        logger.warning("Failed to delete similarity index points doc_id=%s: %s", doc_id, exc)

    query = db.query(TaskRun).filter(TaskRun.task == "similarity_index")
    if doc_id is not None:
        query = query.filter(TaskRun.doc_id == int(doc_id))
    deleted = int(query.delete(synchronize_session=False) or 0)
    db.commit()
    return {"deleted": deleted, "qdrant_deleted": qdrant_deleted, "qdrant_errors": qdrant_errors}


@router.post("/cleanup-texts", response_model=CleanupTextsResponse)
def cleanup_texts(
    payload: CleanupTextsRequest,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> ResponseDict:
    if payload.source and payload.source not in ("paperless_ocr", "vision_ocr", "pdf_text"):
        raise HTTPException(status_code=400, detail="Invalid source")
    doc_ids = [int(doc_id) for doc_id in (payload.doc_ids or []) if int(doc_id) > 0]
    return run_cleanup_texts(
        db=db,
        settings=settings,
        doc_ids=doc_ids,
        source=payload.source,
        clear_first=payload.clear_first,
        enqueue=payload.enqueue,
        queue_enabled=require_queue_enabled(settings),
        enqueue_task_sequence=enqueue_task_sequence,
    )


@router.post("/{doc_id}/operations/enqueue-task", response_model=DocumentOperationEnqueueResponse)
def enqueue_document_task(
    doc_id: int,
    payload: DocumentTaskRequest,
    settings: Settings = Depends(get_settings),
) -> ResponseDict:
    if payload.task not in ALLOWED_DOC_TASKS:
        raise HTTPException(status_code=400, detail="Invalid task")
    if not require_queue_enabled(settings):
        return {"enabled": False, "enqueued": 0, "task": payload.task, "doc_id": doc_id}
    task: dict[str, object] = {"doc_id": int(doc_id), "task": payload.task}
    if payload.source:
        task["source"] = payload.source
    if payload.force:
        task["force"] = True
    if payload.clear_first:
        task["clear_first"] = True
    enqueued = enqueue_task(settings, task)
    return {"enabled": True, "enqueued": enqueued, "task": payload.task, "doc_id": doc_id}


@router.post(
    "/{doc_id}/operations/reset-and-reprocess", response_model=DocumentResetReprocessResponse
)
def reset_and_reprocess_document(
    doc_id: int,
    enqueue: bool = True,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> ResponseDict:
    _clear_doc_intelligence(db, doc_id)
    delete_points_for_doc(settings, doc_id)

    raw = paperless.get_document(settings, doc_id)
    data = DocumentIn.model_validate(raw)
    cache: ReferenceCache = {"correspondents": set(), "document_types": set(), "tags": set()}
    upsert_document(db, settings, data, cache)
    db.commit()

    enqueued = 0
    if enqueue and require_queue_enabled(settings):
        tasks = build_task_sequence(settings, doc_id, include_sync=False, force=True)
        enqueued = enqueue_task_sequence_front(settings, tasks, force=True)
    return {"doc_id": doc_id, "synced": True, "reset": True, "enqueued": enqueued}
