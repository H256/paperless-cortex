from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import get_db
from app.deps import get_settings
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
from app.services.queue import enqueue_task, enqueue_task_sequence, enqueue_task_sequence_front
from app.services.embeddings import delete_points_for_doc
from app.services.pipeline_fanout import build_pipeline_fanout_items, latest_task_runs_by_signature
from app.services.page_text_store import reclean_page_texts
from app.services.queue_tasks import build_task_sequence
from app.services.process_missing import ProcessMissingOptions, process_missing_documents
from app.services.pipeline_planner import (
    PipelineOptions,
    collect_pipeline_cache,
    dedupe_tasks,
    evaluate_doc_pipeline,
    post_sync_followup_tasks,
    task_signature,
)
from app.services import paperless
from app.schemas import DocumentIn
from app.routes.sync import _upsert_document
from app.routes.sync import sync_documents as run_sync_documents
from app.api_models import (
    ClearIntelligenceResponse,
    CleanupTextsResponse,
    DocumentPipelineContinueResponse,
    DocumentPipelineFanoutResponse,
    DocumentPipelineStatusResponse,
    DeleteEmbeddingsResponse,
    DocumentOperationEnqueueResponse,
    DocumentResetReprocessResponse,
    DeleteSuggestionsResponse,
    DeleteVisionOcrResponse,
    ProcessMissingResponse,
    ResetIntelligenceResponse,
)
from app.routes.documents_common import parse_iso
from app.routes.queue_guard import require_queue_enabled

router = APIRouter(prefix="/documents", tags=["documents"])
logger = logging.getLogger(__name__)

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
        cache = {"correspondents": set(), "document_types": set(), "tags": set()}
        _upsert_document(db, settings, data, cache)
        db.commit()
        doc = db.get(Document, int(doc_id))
        if doc:
            logger.info("Auto-synced missing local document doc_id=%s", doc_id)
            return doc
    except Exception:
        logger.warning("Failed to auto-sync missing local document doc_id=%s", doc_id, exc_info=True)
    raise HTTPException(status_code=404, detail="Document not found")


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


def _clear_doc_intelligence(db: Session, doc_id: int) -> None:
    db.query(DocumentSuggestion).filter(DocumentSuggestion.doc_id == doc_id).delete(synchronize_session=False)
    db.query(DocumentPageText).filter(DocumentPageText.doc_id == doc_id).delete(synchronize_session=False)
    db.query(DocumentEmbedding).filter(DocumentEmbedding.doc_id == doc_id).delete(synchronize_session=False)
    db.query(DocumentOcrScore).filter(DocumentOcrScore.doc_id == doc_id).delete(synchronize_session=False)
    db.query(DocumentPageNote).filter(DocumentPageNote.doc_id == doc_id).delete(synchronize_session=False)
    db.query(DocumentSectionSummary).filter(DocumentSectionSummary.doc_id == doc_id).delete(
        synchronize_session=False
    )
    db.query(DocumentPageAnchor).filter(DocumentPageAnchor.doc_id == doc_id).delete(synchronize_session=False)
    # Reset should not keep stale per-doc pipeline history; it confuses fan-out/status views.
    db.query(TaskRun).filter(TaskRun.doc_id == doc_id).delete(synchronize_session=False)
    db.commit()


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
):
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
        run_sync_documents=run_sync_documents,
        enqueue_task_sequence=enqueue_task_sequence,
    )


def _sync_ok(settings: Settings, doc: Document) -> bool:
    try:
        remote = paperless.get_document(settings, int(doc.id))
    except Exception:
        return False
    local_modified = parse_iso(doc.modified) or parse_iso(doc.created)
    remote_modified = parse_iso(remote.get("modified")) or parse_iso(remote.get("created"))
    if not remote_modified:
        return True
    if not local_modified:
        return False
    return local_modified >= remote_modified


@router.get("/{doc_id}/pipeline-status", response_model=DocumentPipelineStatusResponse)
def get_document_pipeline_status(
    doc_id: int,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    doc = _get_or_sync_local_document(db=db, settings=settings, doc_id=int(doc_id))
    cache = collect_pipeline_cache(db, doc_ids={int(doc_id)}, settings=settings)
    options = PipelineOptions()
    evaluation = evaluate_doc_pipeline(doc=doc, settings=settings, cache=cache, options=options)
    sync_ok = _sync_ok(settings, doc)
    if not sync_ok:
        evaluation["tasks"] = [{"doc_id": int(doc_id), "task": "sync"}] + list(evaluation["tasks"])
    preferred_source = str(evaluation["preferred_source"])
    is_large_doc = bool(evaluation["large_doc"])
    paperless_ok = not (
        evaluation["needs_embeddings_paperless"] or evaluation["needs_suggestions_paperless"]
    )
    vision_required = settings.enable_vision_ocr
    vision_ok = True if not vision_required else not (
        evaluation["needs_vision"] or evaluation["needs_embeddings_vision"] or evaluation["needs_suggestions_vision"]
    )
    large_ok = True if not is_large_doc else not (
        evaluation["needs_page_notes"] or evaluation["needs_summary_hierarchical"]
    )
    similarity_ok = not bool(evaluation.get("needs_doc_similarity_index"))
    evidence_required = bool(evaluation.get("evidence_required", True))
    evidence_no_text_layer = bool(evaluation.get("evidence_no_text_layer", False))
    evidence_ok = (not evidence_required) or (not evaluation["needs_evidence_index"])

    steps = [
        {"key": "sync", "required": True, "done": sync_ok, "detail": "Local document is up to date with Paperless."},
        {
            "key": "evidence",
            "required": evidence_required,
            "done": evidence_ok,
            "detail": (
                "Skipped: PDF has no text layer for anchor indexing."
                if evidence_no_text_layer
                else "PDF text-layer anchor index is ready for evidence mapping."
            ),
        },
        {
            "key": "paperless",
            "required": True,
            "done": paperless_ok,
            "detail": "Paperless suggestions and paperless embeddings are ready.",
        },
        {
            "key": "vision",
            "required": vision_required,
            "done": vision_ok if vision_required else True,
            "detail": "Vision OCR, vision suggestions, and vision embeddings are ready.",
        },
        {
            "key": "large",
            "required": is_large_doc,
            "done": large_ok if is_large_doc else True,
            "detail": "Large-doc page notes and hierarchical summary are ready.",
        },
        {
            "key": "similarity",
            "required": True,
            "done": similarity_ok,
            "detail": "Doc-level similarity index is ready.",
        },
    ]
    return {
        "doc_id": int(doc_id),
        "preferred_source": preferred_source,
        "is_large_document": is_large_doc,
        "sync_ok": sync_ok,
        "evidence_ok": evidence_ok,
        "paperless_ok": paperless_ok,
        "vision_ok": vision_ok,
        "large_ok": large_ok,
        "steps": steps,
        "missing_tasks": evaluation["tasks"],
    }


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
):
    doc = _get_or_sync_local_document(db=db, settings=settings, doc_id=int(doc_id))
    if embeddings_mode not in ("auto", "paperless", "vision", "both"):
        raise HTTPException(status_code=400, detail="Invalid embeddings_mode")
    options = PipelineOptions(
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
    cache = collect_pipeline_cache(db, doc_ids={int(doc_id)}, settings=settings)
    evaluation = evaluate_doc_pipeline(doc=doc, settings=settings, cache=cache, options=options)
    if include_sync and not _sync_ok(settings, doc):
        evaluation["tasks"] = [{"doc_id": int(doc_id), "task": "sync"}] + list(evaluation.get("tasks", []))
    planned = post_sync_followup_tasks(int(doc.id), settings=settings, options=options)
    if include_sync:
        planned = [{"doc_id": int(doc.id), "task": "sync"}] + planned
    planned = dedupe_tasks(planned)
    missing_signatures = {task_signature(task) for task in evaluation.get("tasks", [])}
    planned_signatures = {task_signature(task) for task in planned}
    latest_runs = latest_task_runs_by_signature(db, doc_id=int(doc.id), signatures=planned_signatures)
    items = build_pipeline_fanout_items(
        planned_tasks=planned,
        missing_signatures=missing_signatures,
        latest_runs=latest_runs,
        signature_for_task=task_signature,
    )
    return {
        "doc_id": int(doc_id),
        "enabled": bool(settings.queue_enabled),
        "items": items,
    }


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
):
    doc = _get_or_sync_local_document(db=db, settings=settings, doc_id=int(doc_id))
    if embeddings_mode not in ("auto", "paperless", "vision", "both"):
        raise HTTPException(status_code=400, detail="Invalid embeddings_mode")
    if not require_queue_enabled(settings):
        return {"enabled": False, "doc_id": int(doc_id), "dry_run": dry_run, "missing_tasks": 0, "enqueued": 0}

    options = PipelineOptions(
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
    cache = collect_pipeline_cache(db, doc_ids={int(doc_id)}, settings=settings)
    evaluation = evaluate_doc_pipeline(doc=doc, settings=settings, cache=cache, options=options)
    tasks = list(evaluation["tasks"])
    if include_sync and not _sync_ok(settings, doc):
        followups = post_sync_followup_tasks(int(doc_id), settings=settings, options=options)
        if not evaluation.get("needs_evidence_index", False):
            followups = [task for task in followups if str(task.get("task") or "") != "evidence_index"]
        tasks = dedupe_tasks([{"doc_id": int(doc_id), "task": "sync"}] + tasks + followups)
    enqueued = 0
    if tasks and not dry_run:
        enqueued = enqueue_task_sequence(settings, tasks)
    return {
        "enabled": True,
        "doc_id": int(doc_id),
        "dry_run": dry_run,
        "missing_tasks": len(tasks),
        "enqueued": int(enqueued),
    }


@router.post("/reset-intelligence", response_model=ResetIntelligenceResponse)
def reset_intelligence(
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    if not require_queue_enabled(settings):
        return {"enabled": False}
    _clear_intelligence_tables(db)
    return {"enabled": True}


@router.post("/clear-intelligence", response_model=ClearIntelligenceResponse)
def clear_intelligence(
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    if not require_queue_enabled(settings):
        return {"enabled": False}
    _clear_intelligence_tables(db)
    return {"enabled": True}


@router.post("/delete/vision-ocr", response_model=DeleteVisionOcrResponse)
def delete_vision_ocr(
    doc_id: int | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(DocumentPageText).filter(DocumentPageText.source == "vision_ocr")
    if doc_id is not None:
        query = query.filter(DocumentPageText.doc_id == doc_id)
    count = int(query.delete(synchronize_session=False) or 0)
    score_query = db.query(DocumentOcrScore).filter(DocumentOcrScore.source == "vision_ocr")
    if doc_id is not None:
        score_query = score_query.filter(DocumentOcrScore.doc_id == doc_id)
    score_query.delete(synchronize_session=False)
    db.commit()
    return {"deleted": count}


@router.post("/delete/suggestions", response_model=DeleteSuggestionsResponse)
def delete_suggestions(
    doc_id: int | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(DocumentSuggestion)
    if doc_id is not None:
        query = query.filter(DocumentSuggestion.doc_id == doc_id)
    count = int(query.delete(synchronize_session=False) or 0)
    db.commit()
    return {"deleted": count}


@router.post("/delete/embeddings", response_model=DeleteEmbeddingsResponse)
def delete_embeddings(
    doc_id: int | None = None,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    if doc_id is not None:
        delete_points_for_doc(settings, doc_id)
        row = db.get(DocumentEmbedding, doc_id)
        if row:
            db.delete(row)
            db.commit()
        return {"deleted": 1}
    db.query(DocumentEmbedding).delete(synchronize_session=False)
    db.commit()
    return {"deleted": 1}


@router.post("/cleanup-texts", response_model=CleanupTextsResponse)
def cleanup_texts(
    payload: CleanupTextsRequest,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    if payload.source and payload.source not in ("paperless_ocr", "vision_ocr", "pdf_text"):
        raise HTTPException(status_code=400, detail="Invalid source")
    doc_ids = [int(doc_id) for doc_id in (payload.doc_ids or []) if int(doc_id) > 0]
    if payload.enqueue:
        if not require_queue_enabled(settings):
            return {"queued": False, "docs": len(doc_ids), "enqueued": 0, "processed": 0, "updated": 0}
        if not doc_ids:
            doc_ids = [int(row.id) for row in db.query(Document.id).yield_per(500)]
        tasks: list[dict] = []
        for doc_id in doc_ids:
            task: dict[str, object] = {"doc_id": doc_id, "task": "cleanup_texts", "clear_first": payload.clear_first}
            if payload.source:
                task["source"] = payload.source
            tasks.append(task)
        enqueued = enqueue_task_sequence(settings, tasks)
        return {"queued": True, "docs": len(doc_ids), "enqueued": enqueued, "processed": 0, "updated": 0}

    if doc_ids:
        processed_total = 0
        updated_total = 0
        for doc_id in doc_ids:
            result = reclean_page_texts(
                db,
                settings,
                doc_id=doc_id,
                source=payload.source,
                clear_first=payload.clear_first,
            )
            processed_total += result["processed"]
            updated_total += result["updated"]
        return {
            "queued": False,
            "docs": len(doc_ids),
            "enqueued": 0,
            "processed": processed_total,
            "updated": updated_total,
        }

    result = reclean_page_texts(
        db,
        settings,
        doc_id=None,
        source=payload.source,
        clear_first=payload.clear_first,
    )
    docs_count = db.query(DocumentPageText.doc_id).distinct().count()
    return {
        "queued": False,
        "docs": docs_count,
        "enqueued": 0,
        "processed": result["processed"],
        "updated": result["updated"],
    }


@router.post("/{doc_id}/operations/enqueue-task", response_model=DocumentOperationEnqueueResponse)
def enqueue_document_task(
    doc_id: int,
    payload: DocumentTaskRequest,
    settings: Settings = Depends(get_settings),
):
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


@router.post("/{doc_id}/operations/reset-and-reprocess", response_model=DocumentResetReprocessResponse)
def reset_and_reprocess_document(
    doc_id: int,
    enqueue: bool = True,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    _clear_doc_intelligence(db, doc_id)
    delete_points_for_doc(settings, doc_id)

    raw = paperless.get_document(settings, doc_id)
    data = DocumentIn.model_validate(raw)
    cache = {"correspondents": set(), "document_types": set(), "tags": set()}
    _upsert_document(db, settings, data, cache)
    db.commit()

    enqueued = 0
    if enqueue and require_queue_enabled(settings):
        tasks = build_task_sequence(settings, doc_id, include_sync=False, force=True)
        enqueued = enqueue_task_sequence_front(settings, tasks, force=True)
    return {"doc_id": doc_id, "synced": True, "reset": True, "enqueued": enqueued}
