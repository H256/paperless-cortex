from __future__ import annotations

from datetime import datetime
from typing import Any

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
    DocumentPageNote,
    DocumentPageText,
    DocumentSectionSummary,
    DocumentSuggestion,
)
from app.services.queue import enqueue_task, enqueue_task_sequence
from app.services.embeddings import delete_points_for_doc
from app.services.hierarchical_summary import is_large_document
from app.services.page_text_store import reclean_page_texts
from app.services.queue_tasks import build_task_sequence
from app.services import paperless
from app.schemas import DocumentIn
from app.routes.sync import _upsert_document
from app.api_models import (
    ClearIntelligenceResponse,
    CleanupTextsResponse,
    DocumentPipelineContinueResponse,
    DocumentPipelineStatusResponse,
    DeleteEmbeddingsResponse,
    DocumentOperationEnqueueResponse,
    DocumentResetReprocessResponse,
    DeleteSuggestionsResponse,
    DeleteVisionOcrResponse,
    ProcessMissingResponse,
    ResetIntelligenceResponse,
)
from app.routes.documents_common import parse_iso, should_skip_doc
from app.routes.queue_guard import require_queue_enabled

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_DOC_TASKS = {
    "sync",
    "vision_ocr",
    "cleanup_texts",
    "embeddings_paperless",
    "embeddings_vision",
    "page_notes_paperless",
    "page_notes_vision",
    "summary_hierarchical",
    "suggestions_paperless",
    "suggestions_vision",
}


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


class _PipelineOptions(BaseModel):
    include_vision_ocr: bool = True
    include_embeddings: bool = True
    include_embeddings_paperless: bool = True
    include_embeddings_vision: bool = True
    include_page_notes: bool = False
    include_summary_hierarchical: bool = False
    include_suggestions_paperless: bool = True
    include_suggestions_vision: bool = True
    embeddings_mode: str = "auto"


def _is_vision_complete(doc: Document, pages: set[int]) -> bool:
    expected = int(doc.page_count or 0)
    if expected <= 0:
        return bool(pages)
    bounded = {page for page in pages if 1 <= page <= expected}
    return len(bounded) == expected


def _collect_pipeline_cache(db: Session) -> dict[str, Any]:
    embeddings = {int(row.doc_id): row for row in db.query(DocumentEmbedding).all()}
    suggestions = {(int(row.doc_id), str(row.source)): row for row in db.query(DocumentSuggestion).all()}

    vision_rows = db.query(DocumentPageText).filter(DocumentPageText.source == "vision_ocr").all()
    vision_latest: dict[int, datetime] = {}
    vision_pages_by_doc: dict[int, set[int]] = {}
    for row in vision_rows:
        doc_id = int(row.doc_id)
        vision_pages_by_doc.setdefault(doc_id, set()).add(int(row.page))
        created = parse_iso(row.created_at)
        if not created:
            continue
        current = vision_latest.get(doc_id)
        if current is None or created > current:
            vision_latest[doc_id] = created

    page_notes_by_doc_source: dict[tuple[int, str], list[DocumentPageNote]] = {}
    for row in db.query(DocumentPageNote).all():
        page_notes_by_doc_source.setdefault((int(row.doc_id), str(row.source)), []).append(row)

    hier_summaries = {
        int(row.doc_id): row for row in db.query(DocumentSuggestion).filter(DocumentSuggestion.source == "hier_summary").all()
    }
    return {
        "embeddings": embeddings,
        "suggestions": suggestions,
        "vision_latest": vision_latest,
        "vision_pages_by_doc": vision_pages_by_doc,
        "page_notes_by_doc_source": page_notes_by_doc_source,
        "hier_summaries": hier_summaries,
    }


def _evaluate_doc_pipeline(
    *,
    doc: Document,
    settings: Settings,
    cache: dict[str, Any],
    options: _PipelineOptions,
) -> dict[str, Any]:
    tasks: list[dict[str, Any]] = []
    doc_modified = parse_iso(doc.modified) or parse_iso(doc.created)

    embeddings: dict[int, DocumentEmbedding] = cache["embeddings"]
    embedding = embeddings.get(int(doc.id))
    embedded_at = parse_iso(embedding.embedded_at) if embedding else None
    embedding_source = embedding.embedding_source if embedding else None

    suggestions: dict[tuple[int, str], DocumentSuggestion] = cache["suggestions"]
    sugg_p = suggestions.get((int(doc.id), "paperless_ocr"))
    sugg_v = suggestions.get((int(doc.id), "vision_ocr"))
    sugg_p_at = parse_iso(sugg_p.created_at) if sugg_p else None
    sugg_v_at = parse_iso(sugg_v.created_at) if sugg_v else None

    vision_latest: dict[int, datetime] = cache["vision_latest"]
    vision_updated_at = vision_latest.get(int(doc.id))
    vision_pages_by_doc: dict[int, set[int]] = cache["vision_pages_by_doc"]
    has_complete_vision = _is_vision_complete(doc, vision_pages_by_doc.get(int(doc.id), set()))
    needs_vision = options.include_vision_ocr and (
        not has_complete_vision
        or not vision_updated_at
        or (doc_modified and vision_updated_at < doc_modified)
    )
    if needs_vision:
        tasks.append({"doc_id": int(doc.id), "task": "vision_ocr"})

    embeddings_stale = bool(not embedded_at or (doc_modified and embedded_at < doc_modified))
    wants_paperless_embeddings = bool(options.include_embeddings and options.include_embeddings_paperless)
    wants_vision_embeddings = bool(
        options.include_embeddings
        and options.include_embeddings_vision
        and settings.enable_vision_ocr
        and (has_complete_vision or options.include_vision_ocr)
    )
    target_embedding_source: str | None = None
    if options.include_embeddings:
        if options.embeddings_mode == "vision":
            target_embedding_source = "vision" if wants_vision_embeddings else None
        elif options.embeddings_mode == "paperless":
            target_embedding_source = "paperless" if wants_paperless_embeddings else None
        else:
            if wants_vision_embeddings:
                target_embedding_source = "vision"
            elif wants_paperless_embeddings:
                target_embedding_source = "paperless"
    needs_embeddings = bool(target_embedding_source and (embedding_source != target_embedding_source or embeddings_stale))
    needs_embeddings_paperless = needs_embeddings and target_embedding_source == "paperless"
    needs_embeddings_vision = needs_embeddings and target_embedding_source == "vision"
    if needs_embeddings_paperless:
        tasks.append({"doc_id": int(doc.id), "task": "embeddings_paperless"})
    if needs_embeddings_vision:
        tasks.append({"doc_id": int(doc.id), "task": "embeddings_vision"})

    needs_sugg_p = options.include_suggestions_paperless and (not sugg_p_at or (doc_modified and sugg_p_at < doc_modified))
    needs_sugg_v = options.include_suggestions_vision and (not sugg_v_at or (doc_modified and sugg_v_at < doc_modified))

    page_notes_source = "vision_ocr" if settings.enable_vision_ocr and options.include_vision_ocr else "paperless_ocr"
    page_notes_task = "page_notes_vision" if page_notes_source == "vision_ocr" else "page_notes_paperless"
    page_notes_by_doc_source: dict[tuple[int, str], list[DocumentPageNote]] = cache["page_notes_by_doc_source"]
    note_rows = page_notes_by_doc_source.get((int(doc.id), page_notes_source), [])
    ok_notes = [row for row in note_rows if row.status == "ok"]
    note_pages = {
        int(row.page)
        for row in ok_notes
        if getattr(row, "page", None) is not None and int(row.page) > 0
    }
    expected_note_pages = int(doc.page_count or 0)
    notes_complete = len(note_pages) > 0 if expected_note_pages <= 0 else len(note_pages) >= expected_note_pages
    notes_latest_raw = max((parse_iso(row.processed_at) or parse_iso(row.created_at) for row in ok_notes), default=None)
    notes_stale = (
        not notes_latest_raw
        or (doc_modified and notes_latest_raw < doc_modified)
        or (page_notes_source == "vision_ocr" and vision_updated_at is not None and notes_latest_raw < vision_updated_at)
    )
    large_doc = is_large_document(
        page_count=doc.page_count,
        total_text=doc.content,
        threshold_pages=settings.large_doc_page_threshold,
    )
    evaluate_page_notes = options.include_page_notes or options.include_summary_hierarchical
    needs_page_notes = evaluate_page_notes and large_doc and (not notes_complete or bool(notes_stale))
    if needs_page_notes and (options.include_page_notes or options.include_summary_hierarchical):
        tasks.append({"doc_id": int(doc.id), "task": page_notes_task})

    hier_summaries: dict[int, DocumentSuggestion] = cache["hier_summaries"]
    summary_row = hier_summaries.get(int(doc.id))
    summary_at = parse_iso(summary_row.created_at) if summary_row else None
    needs_summary = options.include_summary_hierarchical and large_doc and (
        not summary_at or (doc_modified and summary_at < doc_modified) or (notes_latest_raw and summary_at < notes_latest_raw)
    )
    if needs_summary:
        tasks.append({"doc_id": int(doc.id), "task": "summary_hierarchical", "source": page_notes_source})

    if needs_sugg_p:
        tasks.append({"doc_id": int(doc.id), "task": "suggestions_paperless"})
    if needs_sugg_v:
        tasks.append({"doc_id": int(doc.id), "task": "suggestions_vision"})

    return {
        "doc_id": int(doc.id),
        "tasks": tasks,
        "large_doc": large_doc,
        "preferred_source": page_notes_source,
        "needs_vision": needs_vision,
        "needs_embeddings": needs_embeddings,
        "needs_embeddings_paperless": needs_embeddings_paperless,
        "needs_embeddings_vision": needs_embeddings_vision,
        "needs_suggestions_paperless": needs_sugg_p,
        "needs_suggestions_vision": needs_sugg_v,
        "needs_page_notes": needs_page_notes,
        "needs_summary_hierarchical": needs_summary,
    }


def _clear_intelligence_tables(db: Session) -> None:
    db.execute(delete(DocumentSuggestion))
    db.execute(delete(DocumentPageText))
    db.execute(delete(DocumentEmbedding))
    db.execute(delete(DocumentOcrScore))
    db.execute(delete(DocumentPageNote))
    db.execute(delete(DocumentSectionSummary))
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
    db.commit()


@router.post("/process-missing", response_model=ProcessMissingResponse)
def process_missing(
    dry_run: bool = False,
    include_vision_ocr: bool = True,
    include_embeddings: bool = True,
    include_embeddings_paperless: bool = True,
    include_embeddings_vision: bool = True,
    include_page_notes: bool = False,
    include_summary_hierarchical: bool = False,
    include_suggestions_paperless: bool = True,
    include_suggestions_vision: bool = True,
    embeddings_mode: str = "auto",
    limit: int | None = None,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    if not require_queue_enabled(settings):
        return {"enabled": False, "docs": 0, "enqueued": 0, "tasks": 0, "dry_run": dry_run}
    if embeddings_mode not in ("auto", "paperless", "vision"):
        raise HTTPException(status_code=400, detail="Invalid embeddings_mode")
    if limit is not None and limit < 1:
        raise HTTPException(status_code=400, detail="limit must be >= 1")

    docs = db.query(Document).order_by(Document.id.asc()).all()
    if include_vision_ocr:
        docs.sort(
            key=lambda doc: (
                doc.page_count is None,
                doc.page_count or 0,
                doc.id,
            )
        )
    cache = _collect_pipeline_cache(db)
    options = _PipelineOptions(
        include_vision_ocr=include_vision_ocr,
        include_embeddings=include_embeddings,
        include_embeddings_paperless=include_embeddings_paperless,
        include_embeddings_vision=include_embeddings_vision,
        include_page_notes=include_page_notes,
        include_summary_hierarchical=include_summary_hierarchical,
        include_suggestions_paperless=include_suggestions_paperless,
        include_suggestions_vision=include_suggestions_vision,
        embeddings_mode=embeddings_mode,
    )

    enqueued_docs = 0
    enqueued_tasks = 0
    missing_docs = 0
    missing_vision = 0
    missing_embeddings = 0
    missing_embeddings_paperless = 0
    missing_embeddings_vision = 0
    missing_page_notes = 0
    missing_summary_hier = 0
    missing_sugg_p = 0
    missing_sugg_v = 0
    checked_docs = 0
    selected_for_run = 0
    for doc in docs:
        if should_skip_doc(doc):
            continue
        checked_docs += 1
        evaluation = _evaluate_doc_pipeline(
            doc=doc,
            settings=settings,
            cache=cache,
            options=options,
        )
        tasks = evaluation["tasks"]
        if evaluation["needs_vision"]:
            missing_vision += 1
        if evaluation["needs_embeddings"]:
            missing_embeddings += 1
            if evaluation["needs_embeddings_vision"]:
                missing_embeddings_vision += 1
            if evaluation["needs_embeddings_paperless"]:
                missing_embeddings_paperless += 1
        if options.include_page_notes and evaluation["needs_page_notes"]:
            missing_page_notes += 1
        if evaluation["needs_summary_hierarchical"]:
            missing_summary_hier += 1
        if evaluation["needs_suggestions_paperless"]:
            missing_sugg_p += 1
        if evaluation["needs_suggestions_vision"]:
            missing_sugg_v += 1
        if tasks:
            missing_docs += 1
        if limit is not None and selected_for_run >= limit:
            continue
        if tasks:
            selected_for_run += 1
            if not dry_run:
                enqueued_docs += 1
                enqueued_tasks += enqueue_task_sequence(settings, tasks)

    return {
        "enabled": True,
        "docs": checked_docs,
        "missing_docs": missing_docs,
        "missing_vision_ocr": missing_vision,
        "missing_embeddings": missing_embeddings,
        "missing_embeddings_paperless": missing_embeddings_paperless,
        "missing_embeddings_vision": missing_embeddings_vision,
        "missing_page_notes": missing_page_notes,
        "missing_summary_hierarchical": missing_summary_hier,
        "missing_suggestions_paperless": missing_sugg_p,
        "missing_suggestions_vision": missing_sugg_v,
        "selected": selected_for_run,
        "enqueued": enqueued_docs,
        "tasks": enqueued_tasks,
        "dry_run": dry_run,
    }


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
    doc = db.get(Document, int(doc_id))
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    cache = _collect_pipeline_cache(db)
    options = _PipelineOptions()
    evaluation = _evaluate_doc_pipeline(doc=doc, settings=settings, cache=cache, options=options)
    preferred_source = str(evaluation["preferred_source"])
    is_large_doc = bool(evaluation["large_doc"])

    sync_ok = _sync_ok(settings, doc)
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

    steps = [
        {"key": "sync", "required": True, "done": sync_ok, "detail": "Local document is up to date with Paperless."},
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
    ]
    return {
        "doc_id": int(doc_id),
        "preferred_source": preferred_source,
        "is_large_document": is_large_doc,
        "sync_ok": sync_ok,
        "paperless_ok": paperless_ok,
        "vision_ok": vision_ok,
        "large_ok": large_ok,
        "steps": steps,
        "missing_tasks": evaluation["tasks"],
    }


@router.post("/{doc_id}/pipeline/continue", response_model=DocumentPipelineContinueResponse)
def continue_document_pipeline(
    doc_id: int,
    dry_run: bool = False,
    include_vision_ocr: bool = True,
    include_embeddings: bool = True,
    include_embeddings_paperless: bool = True,
    include_embeddings_vision: bool = True,
    include_page_notes: bool = True,
    include_summary_hierarchical: bool = True,
    include_suggestions_paperless: bool = True,
    include_suggestions_vision: bool = True,
    embeddings_mode: str = "auto",
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    doc = db.get(Document, int(doc_id))
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if embeddings_mode not in ("auto", "paperless", "vision"):
        raise HTTPException(status_code=400, detail="Invalid embeddings_mode")
    if not require_queue_enabled(settings):
        return {"enabled": False, "doc_id": int(doc_id), "dry_run": dry_run, "missing_tasks": 0, "enqueued": 0}

    options = _PipelineOptions(
        include_vision_ocr=include_vision_ocr,
        include_embeddings=include_embeddings,
        include_embeddings_paperless=include_embeddings_paperless,
        include_embeddings_vision=include_embeddings_vision,
        include_page_notes=include_page_notes,
        include_summary_hierarchical=include_summary_hierarchical,
        include_suggestions_paperless=include_suggestions_paperless,
        include_suggestions_vision=include_suggestions_vision,
        embeddings_mode=embeddings_mode,
    )
    cache = _collect_pipeline_cache(db)
    evaluation = _evaluate_doc_pipeline(doc=doc, settings=settings, cache=cache, options=options)
    tasks = evaluation["tasks"]
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
    count = query.count()
    query.delete(synchronize_session=False)
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
    count = query.count()
    query.delete(synchronize_session=False)
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
            doc_ids = [int(row.id) for row in db.query(Document.id).all()]
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
        enqueued = enqueue_task_sequence(settings, tasks)
    return {"doc_id": doc_id, "synced": True, "reset": True, "enqueued": enqueued}
