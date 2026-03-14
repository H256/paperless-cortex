from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, cast

import httpx

from app.config import Settings
from app.models import Document, DocumentPageText
from app.services.documents.document_review import parse_iso_datetime
from app.services.documents.page_text_store import reclean_page_texts
from app.services.integrations import paperless
from app.services.pipeline.pipeline_fanout import (
    build_pipeline_fanout_items,
    latest_task_runs_by_signature,
)
from app.services.pipeline.pipeline_planner import (
    PipelineOptions,
    collect_pipeline_cache,
    dedupe_tasks,
    evaluate_doc_pipeline,
    post_sync_followup_tasks,
    task_signature,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

ResponseDict = dict[str, object]
TaskPayload = dict[str, object]
EnqueueTaskSequence = Callable[[Settings, list[TaskPayload]], int]

_VALID_EMBEDDINGS_MODES = {"auto", "paperless", "vision", "both"}


def validate_embeddings_mode(mode: str) -> None:
    if mode not in _VALID_EMBEDDINGS_MODES:
        raise ValueError("Invalid embeddings_mode")


def build_pipeline_options(
    *,
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
) -> PipelineOptions:
    validate_embeddings_mode(embeddings_mode)
    return PipelineOptions(
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


def is_document_sync_ok(settings: Settings, doc: Document) -> bool:
    try:
        remote = paperless.get_document(settings, int(doc.id))
    except (httpx.HTTPError, RuntimeError, ValueError):
        return False
    local_modified = parse_iso_datetime(doc.modified) or parse_iso_datetime(doc.created)
    remote_modified = parse_iso_datetime(remote.get("modified")) or parse_iso_datetime(
        remote.get("created")
    )
    if not remote_modified:
        return True
    if not local_modified:
        return False
    return local_modified >= remote_modified


def _evaluate_pipeline(
    *,
    doc_id: int,
    doc: Document,
    settings: Settings,
    db: Session,
    options: PipelineOptions,
) -> dict[str, object]:
    cache = collect_pipeline_cache(db, doc_ids={doc_id}, settings=settings)
    return evaluate_doc_pipeline(doc=doc, settings=settings, cache=cache, options=options)


def build_document_pipeline_status_payload(
    *,
    doc_id: int,
    doc: Document,
    settings: Settings,
    db: Session,
) -> ResponseDict:
    evaluation = _evaluate_pipeline(
        doc_id=doc_id,
        doc=doc,
        settings=settings,
        db=db,
        options=PipelineOptions(),
    )
    sync_ok = is_document_sync_ok(settings, doc)
    tasks = list(cast("list[TaskPayload]", evaluation["tasks"]))
    if not sync_ok:
        tasks = [{"doc_id": doc_id, "task": "sync"}, *tasks]
    preferred_source = str(evaluation["preferred_source"])
    is_large_doc = bool(evaluation["large_doc"])
    paperless_ok = not (
        bool(evaluation["needs_embeddings_paperless"])
        or bool(evaluation["needs_suggestions_paperless"])
    )
    vision_required = settings.enable_vision_ocr
    vision_ok = (
        True
        if not vision_required
        else not (
            bool(evaluation["needs_vision"])
            or bool(evaluation["needs_embeddings_vision"])
            or bool(evaluation["needs_suggestions_vision"])
        )
    )
    large_ok = (
        True
        if not is_large_doc
        else not (
            bool(evaluation["needs_page_notes"])
            or bool(evaluation["needs_summary_hierarchical"])
        )
    )
    similarity_ok = not bool(evaluation.get("needs_doc_similarity_index"))
    evidence_required = bool(evaluation.get("evidence_required", True))
    evidence_no_text_layer = bool(evaluation.get("evidence_no_text_layer", False))
    evidence_ok = (not evidence_required) or (not bool(evaluation["needs_evidence_index"]))

    steps = [
        {
            "key": "sync",
            "required": True,
            "done": sync_ok,
            "detail": "Local document is up to date with Paperless.",
        },
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
        "doc_id": doc_id,
        "preferred_source": preferred_source,
        "is_large_document": is_large_doc,
        "sync_ok": sync_ok,
        "evidence_ok": evidence_ok,
        "paperless_ok": paperless_ok,
        "vision_ok": vision_ok,
        "large_ok": large_ok,
        "steps": steps,
        "missing_tasks": tasks,
    }


def build_document_pipeline_fanout_payload(
    *,
    doc_id: int,
    doc: Document,
    settings: Settings,
    db: Session,
    options: PipelineOptions,
) -> ResponseDict:
    evaluation = _evaluate_pipeline(doc_id=doc_id, doc=doc, settings=settings, db=db, options=options)
    missing_tasks = list(cast("list[TaskPayload]", evaluation.get("tasks", [])))
    if options.include_sync and not is_document_sync_ok(settings, doc):
        missing_tasks = [{"doc_id": doc_id, "task": "sync"}, *missing_tasks]
    planned = post_sync_followup_tasks(doc_id, settings=settings, options=options)
    if options.include_sync:
        planned = [{"doc_id": doc_id, "task": "sync"}, *planned]
    planned = dedupe_tasks(planned)
    missing_signatures = {task_signature(task) for task in missing_tasks}
    planned_signatures = {task_signature(task) for task in planned}
    latest_runs = latest_task_runs_by_signature(db, doc_id=doc_id, signatures=planned_signatures)
    items = build_pipeline_fanout_items(
        planned_tasks=planned,
        missing_signatures=missing_signatures,
        latest_runs=latest_runs,
        signature_for_task=task_signature,
    )
    return {"doc_id": doc_id, "enabled": bool(settings.queue_enabled), "items": items}


def continue_document_pipeline_payload(
    *,
    doc_id: int,
    doc: Document,
    settings: Settings,
    db: Session,
    options: PipelineOptions,
    dry_run: bool,
    queue_enabled: bool,
    enqueue_task_sequence: EnqueueTaskSequence,
) -> ResponseDict:
    if not queue_enabled:
        return {
            "enabled": False,
            "doc_id": doc_id,
            "dry_run": dry_run,
            "missing_tasks": 0,
            "enqueued": 0,
        }
    evaluation = _evaluate_pipeline(doc_id=doc_id, doc=doc, settings=settings, db=db, options=options)
    tasks = list(cast("list[TaskPayload]", evaluation["tasks"]))
    if options.include_sync and not is_document_sync_ok(settings, doc):
        followups = post_sync_followup_tasks(doc_id, settings=settings, options=options)
        if not bool(evaluation.get("needs_evidence_index", False)):
            followups = [
                task for task in followups if str(task.get("task") or "") != "evidence_index"
            ]
        tasks = dedupe_tasks([{"doc_id": doc_id, "task": "sync"}, *tasks, *followups])
    enqueued = 0
    if tasks and not dry_run:
        enqueued = enqueue_task_sequence(settings, tasks)
    return {
        "enabled": True,
        "doc_id": doc_id,
        "dry_run": dry_run,
        "missing_tasks": len(tasks),
        "enqueued": int(enqueued),
    }


def run_cleanup_texts(
    *,
    db: Session,
    settings: Settings,
    doc_ids: list[int],
    source: str | None,
    clear_first: bool,
    enqueue: bool,
    queue_enabled: bool,
    enqueue_task_sequence: EnqueueTaskSequence,
) -> ResponseDict:
    if enqueue:
        if not queue_enabled:
            return {
                "queued": False,
                "docs": len(doc_ids),
                "enqueued": 0,
                "processed": 0,
                "updated": 0,
            }
        target_doc_ids = doc_ids or [int(row.id) for row in db.query(Document.id).yield_per(500)]
        tasks: list[TaskPayload] = []
        for doc_id in target_doc_ids:
            task: TaskPayload = {
                "doc_id": doc_id,
                "task": "cleanup_texts",
                "clear_first": clear_first,
            }
            if source:
                task["source"] = source
            tasks.append(task)
        enqueued = enqueue_task_sequence(settings, tasks)
        return {
            "queued": True,
            "docs": len(target_doc_ids),
            "enqueued": enqueued,
            "processed": 0,
            "updated": 0,
        }

    if doc_ids:
        processed_total = 0
        updated_total = 0
        for doc_id in doc_ids:
            result = reclean_page_texts(
                db,
                settings,
                doc_id=doc_id,
                source=source,
                clear_first=clear_first,
            )
            processed_total += int(result["processed"])
            updated_total += int(result["updated"])
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
        source=source,
        clear_first=clear_first,
    )
    docs_count = int(db.query(DocumentPageText.doc_id).distinct().count())
    return {
        "queued": False,
        "docs": docs_count,
        "enqueued": 0,
        "processed": int(result["processed"]),
        "updated": int(result["updated"]),
    }
