from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, delete, or_
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
from app.services.queue import enqueue_task, enqueue_task_sequence
from app.services.embeddings import delete_points_for_doc
from app.services.hierarchical_summary import is_large_document
from app.services.page_text_store import reclean_page_texts
from app.services.queue_tasks import build_task_sequence
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
from app.routes.documents_common import parse_iso, should_skip_doc
from app.routes.queue_guard import require_queue_enabled

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_DOC_TASKS = {
    "sync",
    "evidence_index",
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
    include_sync: bool = False
    include_evidence_index: bool = True
    include_vision_ocr: bool = True
    include_embeddings: bool = True
    include_embeddings_paperless: bool = True
    include_embeddings_vision: bool = True
    include_page_notes: bool = True
    include_summary_hierarchical: bool = True
    include_suggestions_paperless: bool = True
    include_suggestions_vision: bool = True
    embeddings_mode: str = "auto"


def _task_identity(task: dict[str, Any]) -> tuple:
    return (
        int(task.get("doc_id") or 0),
        str(task.get("task") or ""),
        str(task.get("source") or ""),
        bool(task.get("force") or False),
        bool(task.get("clear_first") or False),
    )


def _task_signature(task: dict[str, Any]) -> tuple[str, str]:
    return (
        str(task.get("task") or "").strip(),
        str(task.get("source") or "").strip(),
    )


def _dedupe_tasks(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple] = set()
    deduped: list[dict[str, Any]] = []
    for task in tasks:
        key = _task_identity(task)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(task)
    return deduped


def _post_sync_followup_tasks(doc_id: int, *, settings: Settings, options: _PipelineOptions) -> list[dict[str, Any]]:
    normalized = int(doc_id)
    tasks: list[dict[str, Any]] = []
    if options.include_evidence_index:
        tasks.append({"doc_id": normalized, "task": "evidence_index"})
    use_vision = bool(settings.enable_vision_ocr and options.include_vision_ocr)

    if options.include_embeddings:
        if options.embeddings_mode == "paperless":
            if options.include_embeddings_paperless:
                tasks.append({"doc_id": normalized, "task": "embeddings_paperless"})
        elif options.embeddings_mode == "vision":
            if options.include_embeddings_vision and use_vision:
                tasks.append({"doc_id": normalized, "task": "embeddings_vision"})
        elif options.embeddings_mode == "both":
            if options.include_embeddings_paperless:
                tasks.append({"doc_id": normalized, "task": "embeddings_paperless"})
            if options.include_embeddings_vision and use_vision:
                tasks.append({"doc_id": normalized, "task": "embeddings_vision"})
        else:
            # auto
            if use_vision and options.include_embeddings_vision:
                tasks.append({"doc_id": normalized, "task": "embeddings_vision"})
            elif options.include_embeddings_paperless:
                tasks.append({"doc_id": normalized, "task": "embeddings_paperless"})

    if use_vision:
        if options.include_vision_ocr:
            tasks.append({"doc_id": normalized, "task": "vision_ocr"})
        if options.include_page_notes or options.include_summary_hierarchical:
            tasks.append({"doc_id": normalized, "task": "page_notes_vision"})
        if options.include_summary_hierarchical:
            tasks.append({"doc_id": normalized, "task": "summary_hierarchical", "source": "vision_ocr"})
        if options.include_suggestions_paperless:
            tasks.append({"doc_id": normalized, "task": "suggestions_paperless"})
        if options.include_suggestions_vision:
            tasks.append({"doc_id": normalized, "task": "suggestions_vision"})
    else:
        if options.include_page_notes or options.include_summary_hierarchical:
            tasks.append({"doc_id": normalized, "task": "page_notes_paperless"})
        if options.include_summary_hierarchical:
            tasks.append({"doc_id": normalized, "task": "summary_hierarchical", "source": "paperless_ocr"})
        if options.include_suggestions_paperless:
            tasks.append({"doc_id": normalized, "task": "suggestions_paperless"})

    return _dedupe_tasks(tasks)


def _is_vision_complete(doc: Document, pages: set[int]) -> bool:
    expected = int(doc.page_count or 0)
    if expected <= 0:
        return bool(pages)
    bounded = {page for page in pages if 1 <= page <= expected}
    return len(bounded) == expected


def _collect_pipeline_cache(db: Session, *, doc_ids: set[int] | None = None) -> dict[str, Any]:
    id_filter = None
    if doc_ids:
        normalized = {int(doc_id) for doc_id in doc_ids if int(doc_id) > 0}
        if normalized:
            id_filter = normalized

    embedding_query = db.query(DocumentEmbedding.doc_id, DocumentEmbedding.embedding_source)
    if id_filter:
        embedding_query = embedding_query.filter(DocumentEmbedding.doc_id.in_(id_filter))
    embeddings = {
        int(doc_id): str(source or "")
        for doc_id, source in embedding_query.all()
    }

    suggestion_query = db.query(DocumentSuggestion.doc_id, DocumentSuggestion.source, DocumentSuggestion.created_at)
    if id_filter:
        suggestion_query = suggestion_query.filter(DocumentSuggestion.doc_id.in_(id_filter))
    suggestions: set[tuple[int, str]] = set()
    hier_summaries: dict[int, str | None] = {}
    for doc_id, source, created_at in suggestion_query.all():
        normalized_doc_id = int(doc_id)
        normalized_source = str(source or "")
        suggestions.add((normalized_doc_id, normalized_source))
        if normalized_source == "hier_summary":
            hier_summaries[normalized_doc_id] = str(created_at) if created_at else None

    vision_query = (
        db.query(DocumentPageText.doc_id, DocumentPageText.page, DocumentPageText.created_at)
        .filter(DocumentPageText.source == "vision_ocr")
    )
    if id_filter:
        vision_query = vision_query.filter(DocumentPageText.doc_id.in_(id_filter))
    vision_rows = vision_query.all()
    vision_latest: dict[int, datetime] = {}
    vision_pages_by_doc: dict[int, set[int]] = {}
    for doc_id, page, created_at in vision_rows:
        if page is None:
            continue
        normalized_doc_id = int(doc_id)
        vision_pages_by_doc.setdefault(normalized_doc_id, set()).add(int(page))
        created = parse_iso(str(created_at) if created_at else None)
        if not created:
            continue
        current = vision_latest.get(normalized_doc_id)
        if current is None or created > current:
            vision_latest[normalized_doc_id] = created

    page_notes_query = db.query(
        DocumentPageNote.doc_id,
        DocumentPageNote.source,
        DocumentPageNote.page,
        DocumentPageNote.status,
        DocumentPageNote.processed_at,
        DocumentPageNote.created_at,
    )
    if id_filter:
        page_notes_query = page_notes_query.filter(DocumentPageNote.doc_id.in_(id_filter))
    page_notes_by_doc_source: dict[tuple[int, str], list[tuple[int, str, str | None, str | None]]] = {}
    for doc_id, source, page, status, processed_at, created_at in page_notes_query.all():
        if page is None:
            continue
        key = (int(doc_id), str(source or ""))
        page_notes_by_doc_source.setdefault(key, []).append(
            (
                int(page),
                str(status or ""),
                str(processed_at) if processed_at else None,
                str(created_at) if created_at else None,
            )
        )

    anchors_query = (
        db.query(DocumentPageAnchor.doc_id, DocumentPageAnchor.page, DocumentPageAnchor.status, DocumentPageAnchor.token_count)
        .filter(DocumentPageAnchor.source == "paperless_pdf")
    )
    if id_filter:
        anchors_query = anchors_query.filter(DocumentPageAnchor.doc_id.in_(id_filter))
    anchors_by_doc: dict[int, list[tuple[int, str, int]]] = {}
    for doc_id, page, status, token_count in anchors_query.all():
        if page is None:
            continue
        anchors_by_doc.setdefault(int(doc_id), []).append((int(page), str(status or ""), int(token_count or 0)))

    return {
        "embeddings": embeddings,
        "suggestions": suggestions,
        "vision_latest": vision_latest,
        "vision_pages_by_doc": vision_pages_by_doc,
        "page_notes_by_doc_source": page_notes_by_doc_source,
        "anchors_by_doc": anchors_by_doc,
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
    anchors_by_doc: dict[int, list[tuple[int, str, int]]] = cache["anchors_by_doc"]
    anchor_rows = anchors_by_doc.get(int(doc.id), [])
    expected_anchor_pages = int(doc.page_count or 0)
    completed_anchor_pages = {
        int(page)
        for page, status, _token_count in anchor_rows
        if status in {"ok", "no_text_layer"}
    }
    has_evidence_index = (
        len(completed_anchor_pages) > 0
        if expected_anchor_pages <= 0
        else len(completed_anchor_pages) >= expected_anchor_pages
    )
    has_text_layer = any(
        status == "ok" and int(token_count or 0) > 0 for _page, status, token_count in anchor_rows
    )
    no_text_layer_complete = bool(anchor_rows) and has_evidence_index and not has_text_layer
    anchor_has_errors = any(status == "error" for _page, status, _token_count in anchor_rows)
    evidence_required = not no_text_layer_complete
    needs_evidence_index = options.include_evidence_index and evidence_required and (
        (not has_evidence_index) or anchor_has_errors
    )
    if needs_evidence_index:
        tasks.append({"doc_id": int(doc.id), "task": "evidence_index"})

    embeddings: dict[int, str] = cache["embeddings"]
    embedding_source = embeddings.get(int(doc.id))

    suggestions: set[tuple[int, str]] = cache["suggestions"]
    sugg_p = (int(doc.id), "paperless_ocr") in suggestions
    sugg_v = (int(doc.id), "vision_ocr") in suggestions

    vision_latest: dict[int, datetime] = cache["vision_latest"]
    vision_updated_at = vision_latest.get(int(doc.id))
    vision_pages_by_doc: dict[int, set[int]] = cache["vision_pages_by_doc"]
    has_complete_vision = _is_vision_complete(doc, vision_pages_by_doc.get(int(doc.id), set()))
    needs_vision = options.include_vision_ocr and (
        not has_complete_vision
        or not vision_updated_at
    )
    if needs_vision:
        tasks.append({"doc_id": int(doc.id), "task": "vision_ocr"})

    wants_paperless_embeddings = bool(options.include_embeddings and options.include_embeddings_paperless)
    wants_vision_embeddings = bool(
        options.include_embeddings
        and options.include_embeddings_vision
        and settings.enable_vision_ocr
        and (has_complete_vision or options.include_vision_ocr)
    )
    needs_embeddings_paperless = False
    needs_embeddings_vision = False
    if options.include_embeddings:
        mode = (options.embeddings_mode or "auto").strip().lower()
        has_paperless_embedding = embedding_source in {"paperless", "both"}
        has_vision_embedding = embedding_source in {"vision", "both"}
        if mode == "paperless":
            needs_embeddings_paperless = wants_paperless_embeddings and (not has_paperless_embedding)
        elif mode == "vision":
            needs_embeddings_vision = wants_vision_embeddings and (not has_vision_embedding)
        elif mode == "both":
            needs_embeddings_paperless = wants_paperless_embeddings and (not has_paperless_embedding)
            needs_embeddings_vision = wants_vision_embeddings and (not has_vision_embedding)
        else:
            if wants_vision_embeddings:
                needs_embeddings_vision = not has_vision_embedding
            elif wants_paperless_embeddings:
                needs_embeddings_paperless = not has_paperless_embedding
    needs_embeddings = bool(needs_embeddings_paperless or needs_embeddings_vision)
    if needs_embeddings_paperless:
        tasks.append({"doc_id": int(doc.id), "task": "embeddings_paperless"})
    if needs_embeddings_vision:
        tasks.append({"doc_id": int(doc.id), "task": "embeddings_vision"})

    needs_sugg_p = options.include_suggestions_paperless and (not sugg_p)
    needs_sugg_v = options.include_suggestions_vision and (not sugg_v)

    page_notes_source = "vision_ocr" if settings.enable_vision_ocr and options.include_vision_ocr else "paperless_ocr"
    page_notes_task = "page_notes_vision" if page_notes_source == "vision_ocr" else "page_notes_paperless"
    page_notes_by_doc_source: dict[tuple[int, str], list[tuple[int, str, str | None, str | None]]] = cache[
        "page_notes_by_doc_source"
    ]
    note_rows = page_notes_by_doc_source.get((int(doc.id), page_notes_source), [])
    ok_notes = [row for row in note_rows if row[1] == "ok"]
    note_pages = {
        int(page)
        for page, _status, _processed_at, _created_at in ok_notes
        if page is not None and int(page) > 0
    }
    expected_note_pages = int(doc.page_count or 0)
    notes_complete = len(note_pages) > 0 if expected_note_pages <= 0 else len(note_pages) >= expected_note_pages
    notes_latest_raw = max((parse_iso(processed_at) or parse_iso(created_at) for _p, _s, processed_at, created_at in ok_notes), default=None)
    notes_stale = (
        not notes_latest_raw
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

    hier_summaries: dict[int, str | None] = cache["hier_summaries"]
    summary_at = parse_iso(hier_summaries.get(int(doc.id)))
    needs_summary = options.include_summary_hierarchical and large_doc and (
        not summary_at or (notes_latest_raw and summary_at < notes_latest_raw)
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
        "needs_evidence_index": needs_evidence_index,
        "evidence_required": evidence_required,
        "evidence_no_text_layer": no_text_layer_complete,
    }


def _latest_task_runs_by_signature(
    db: Session,
    *,
    doc_id: int,
    signatures: set[tuple[str, str]] | None = None,
) -> dict[tuple[str, str], TaskRun]:
    query = db.query(TaskRun).filter(TaskRun.doc_id == int(doc_id))
    if signatures:
        signature_filters = []
        for task, source in signatures:
            if not task:
                continue
            if source:
                signature_filters.append(and_(TaskRun.task == task, TaskRun.source == source))
            else:
                signature_filters.append(
                    and_(TaskRun.task == task, or_(TaskRun.source.is_(None), TaskRun.source == ""))
                )
        if signature_filters:
            query = query.filter(or_(*signature_filters))
    rows = query.order_by(TaskRun.id.desc()).all()
    latest: dict[tuple[str, str], TaskRun] = {}
    for row in rows:
        key = (str(row.task or "").strip(), str(row.source or "").strip())
        if key in latest:
            continue
        latest[key] = row
        if signatures and len(latest) >= len(signatures):
            break
    return latest


def _fanout_status_from_state(*, is_missing: bool, run: TaskRun | None) -> str:
    if run and str(run.status or "") in {"running", "retrying"}:
        return str(run.status)
    if run and str(run.status or "") == "failed":
        return "failed"
    if is_missing:
        return "missing"
    return "done"


def _build_pipeline_fanout_items(
    *,
    db: Session,
    doc: Document,
    settings: Settings,
    options: _PipelineOptions,
    evaluation: dict[str, Any],
    include_sync: bool,
) -> list[dict[str, Any]]:
    planned = _post_sync_followup_tasks(int(doc.id), settings=settings, options=options)
    if include_sync:
        planned = [{"doc_id": int(doc.id), "task": "sync"}] + planned
    planned = _dedupe_tasks(planned)
    missing_signatures = {_task_signature(task) for task in evaluation.get("tasks", [])}
    planned_signatures = {_task_signature(task) for task in planned}
    latest_runs = _latest_task_runs_by_signature(db, doc_id=int(doc.id), signatures=planned_signatures)

    items: list[dict[str, Any]] = []
    for index, task in enumerate(planned, start=1):
        signature = _task_signature(task)
        run = latest_runs.get(signature)
        checkpoint = None
        if run and run.checkpoint_json:
            raw = str(run.checkpoint_json).strip()
            if raw.startswith(("{", "[")):
                try:
                    parsed = json.loads(raw)
                except Exception:
                    parsed = None
                if isinstance(parsed, dict):
                    checkpoint = parsed
        status = _fanout_status_from_state(is_missing=signature in missing_signatures, run=run)
        detail = f"{task['task']} ({task.get('source') or 'default'})"
        items.append(
            {
                "order": index,
                "task": str(task.get("task") or ""),
                "source": task.get("source"),
                "status": status,
                "detail": detail,
                "checkpoint": checkpoint,
                "error_type": run.error_type if run else None,
                "error_message": run.error_message if run else None,
                "last_started_at": run.started_at if run else None,
                "last_finished_at": run.finished_at if run else None,
            }
        )
    return items


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
    if include_sync:
        run_sync_documents(
            page_size=200,
            incremental=True,
            embed=False,
            page=1,
            page_only=False,
            force_embed=False,
            mark_missing=True,
            insert_only=True,
            settings=settings,
            db=db,
        )

    docs_query = db.query(Document)
    if include_vision_ocr:
        docs_query = docs_query.order_by(Document.page_count.is_(None).asc(), Document.page_count.asc(), Document.id.asc())
    else:
        docs_query = docs_query.order_by(Document.id.asc())
    options = _PipelineOptions(
        include_sync=include_sync,
        include_evidence_index=include_evidence_index,
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
    missing_evidence_index = 0
    missing_sugg_p = 0
    missing_sugg_v = 0
    checked_docs = 0
    selected_for_run = 0
    missing_by_step = {"paperless": 0, "vision": 0, "large": 0}
    preview_docs: list[dict[str, Any]] = []
    preview_docs_limit = 20
    batch_docs: list[Document] = []
    batch_size = 250

    def _process_batch(docs_batch: list[Document]) -> None:
        nonlocal checked_docs
        nonlocal missing_docs
        nonlocal missing_vision
        nonlocal missing_embeddings
        nonlocal missing_embeddings_paperless
        nonlocal missing_embeddings_vision
        nonlocal missing_page_notes
        nonlocal missing_summary_hier
        nonlocal missing_evidence_index
        nonlocal missing_sugg_p
        nonlocal missing_sugg_v
        nonlocal selected_for_run
        nonlocal enqueued_docs
        nonlocal enqueued_tasks
        if not docs_batch:
            return
        cache = _collect_pipeline_cache(db, doc_ids={int(doc.id) for doc in docs_batch})
        for doc in docs_batch:
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
            if evaluation["needs_evidence_index"]:
                missing_evidence_index += 1
            if evaluation["needs_suggestions_paperless"]:
                missing_sugg_p += 1
            if evaluation["needs_suggestions_vision"]:
                missing_sugg_v += 1
            missing_steps: list[str] = []
            if evaluation["needs_embeddings_paperless"] or evaluation["needs_suggestions_paperless"]:
                missing_steps.append("paperless")
                missing_by_step["paperless"] += 1
            if (
                evaluation["needs_vision"]
                or evaluation["needs_embeddings_vision"]
                or evaluation["needs_suggestions_vision"]
            ):
                missing_steps.append("vision")
                missing_by_step["vision"] += 1
            if evaluation["needs_page_notes"] or evaluation["needs_summary_hierarchical"]:
                missing_steps.append("large")
                missing_by_step["large"] += 1
            if tasks:
                missing_docs += 1
                if len(preview_docs) < preview_docs_limit:
                    preview_docs.append(
                        {
                            "doc_id": int(doc.id),
                            "title": str(doc.title or f"Document {doc.id}"),
                            "missing_steps": missing_steps,
                            "missing_tasks": [str(task.get("task") or "") for task in tasks if isinstance(task, dict)],
                        }
                    )
            if limit is not None and selected_for_run >= limit:
                continue
            if tasks:
                selected_for_run += 1
                if not dry_run:
                    enqueued_docs += 1
                    enqueued_tasks += enqueue_task_sequence(settings, tasks)

    for doc in docs_query.yield_per(batch_size):
        batch_docs.append(doc)
        if len(batch_docs) >= batch_size:
            _process_batch(batch_docs)
            batch_docs = []
    _process_batch(batch_docs)

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
        "missing_evidence_index": missing_evidence_index,
        "missing_suggestions_paperless": missing_sugg_p,
        "missing_suggestions_vision": missing_sugg_v,
        "missing_by_step": missing_by_step,
        "preview_docs": preview_docs,
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
    cache = _collect_pipeline_cache(db, doc_ids={int(doc_id)})
    options = _PipelineOptions()
    evaluation = _evaluate_doc_pipeline(doc=doc, settings=settings, cache=cache, options=options)
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
    if embeddings_mode not in ("auto", "paperless", "vision", "both"):
        raise HTTPException(status_code=400, detail="Invalid embeddings_mode")
    options = _PipelineOptions(
        include_sync=include_sync,
        include_evidence_index=include_evidence_index,
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
    cache = _collect_pipeline_cache(db, doc_ids={int(doc_id)})
    evaluation = _evaluate_doc_pipeline(doc=doc, settings=settings, cache=cache, options=options)
    if include_sync and not _sync_ok(settings, doc):
        evaluation["tasks"] = [{"doc_id": int(doc_id), "task": "sync"}] + list(evaluation.get("tasks", []))
    items = _build_pipeline_fanout_items(
        db=db,
        doc=doc,
        settings=settings,
        options=options,
        evaluation=evaluation,
        include_sync=include_sync,
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
    if embeddings_mode not in ("auto", "paperless", "vision", "both"):
        raise HTTPException(status_code=400, detail="Invalid embeddings_mode")
    if not require_queue_enabled(settings):
        return {"enabled": False, "doc_id": int(doc_id), "dry_run": dry_run, "missing_tasks": 0, "enqueued": 0}

    options = _PipelineOptions(
        include_sync=include_sync,
        include_evidence_index=include_evidence_index,
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
    cache = _collect_pipeline_cache(db, doc_ids={int(doc_id)})
    evaluation = _evaluate_doc_pipeline(doc=doc, settings=settings, cache=cache, options=options)
    tasks = list(evaluation["tasks"])
    if include_sync and not _sync_ok(settings, doc):
        followups = _post_sync_followup_tasks(int(doc_id), settings=settings, options=options)
        if not evaluation.get("needs_evidence_index", False):
            followups = [task for task in followups if str(task.get("task") or "") != "evidence_index"]
        tasks = _dedupe_tasks([{"doc_id": int(doc_id), "task": "sync"}] + tasks + followups)
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
