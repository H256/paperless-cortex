from __future__ import annotations

import logging
import os
import socket
import threading
import time
from typing import TYPE_CHECKING

import httpx
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError

from app.config import load_settings
from app.db import SessionLocal
from app.exceptions import WorkerError
from app.models import (
    Document,
    DocumentPageText,
)
from app.services.ai import vision_ocr
from app.services.ai.hierarchical_summary import (
    generate_page_notes,
    is_large_document,
    upsert_page_note,
)
from app.services.ai.hierarchical_summary_pipeline import HierarchicalSummaryPipeline
from app.services.ai.ocr_scoring import ensure_document_ocr_score
from app.services.ai.suggestion_store import (
    audit_suggestion_run,
    persist_suggestions,
    upsert_suggestion,
)
from app.services.ai.suggestions import generate_field_variants, generate_normalized_suggestions
from app.services.documents.documents import fetch_pdf_bytes_for_doc, get_document_or_none
from app.services.documents.page_text_store import reclean_page_texts, upsert_page_texts
from app.services.documents.page_texts_merge import collect_page_texts
from app.services.documents.text_cleaning import clean_ocr_text
from app.services.documents.text_pages import get_baseline_page_texts
from app.services.integrations import paperless
from app.services.integrations.meta_cache import get_cached_correspondents, get_cached_tags
from app.services.pipeline.error_types import (
    classify_worker_error,
    is_retryable_error_type,
    task_source_from_payload,
)
from app.services.pipeline.queue import (
    QUEUE_KEY,
    QUEUE_SET,
    _get_client,
    acquire_worker_lock,
    add_dead_letter,
    clear_cancel,
    clear_queue,
    clear_running_task,
    enqueue_task_delayed,
    is_cancel_requested,
    is_paused,
    mark_done,
    mark_in_progress,
    mark_worker_heartbeat,
    move_due_delayed_tasks,
    record_last_run,
    refresh_worker_lock,
    release_worker_lock,
    reset_stats,
    set_running_task,
    task_key,
)
from app.services.pipeline.task_runs import (
    create_task_run,
    find_latest_checkpoint,
    finish_task_run,
)
from app.services.pipeline.worker_checkpoint import (
    get_task_run_checkpoint as _get_task_run_checkpoint,
)
from app.services.pipeline.worker_checkpoint import (
    resume_stage_current as _resume_stage_current,
)
from app.services.pipeline.worker_checkpoint import (
    set_task_checkpoint as _set_task_checkpoint,
)
from app.services.pipeline.worker_document_tasks import (
    embed_with_pages as _service_embed_with_pages,
)
from app.services.pipeline.worker_document_tasks import (
    process_embeddings_paperless as _service_process_embeddings_paperless,
)
from app.services.pipeline.worker_document_tasks import (
    process_embeddings_vision as _service_process_embeddings_vision,
)
from app.services.pipeline.worker_document_tasks import (
    process_evidence_index as _service_process_evidence_index,
)
from app.services.pipeline.worker_document_tasks import (
    process_similarity_index as _service_process_similarity_index,
)
from app.services.pipeline.worker_document_tasks import (
    process_sync_only as _service_process_sync_only,
)
from app.services.pipeline.worker_runtime import (
    dispatch_worker_task,
    handle_worker_cancel_request,
    parse_worker_queue_item,
)
from app.services.pipeline.worker_suggestion_tasks import (
    build_distilled_context_from_hier_summary as _service_build_distilled_context_from_hier_summary,
)
from app.services.pipeline.worker_suggestion_tasks import (
    build_distilled_context_from_page_notes as _service_build_distilled_context_from_page_notes,
)
from app.services.pipeline.worker_suggestion_tasks import (
    join_page_texts_limited as _service_join_page_texts_limited,
)
from app.services.pipeline.worker_suggestion_tasks import (
    process_suggest_field as _service_process_suggest_field,
)
from app.services.pipeline.worker_suggestion_tasks import (
    process_suggestions_paperless as _service_process_suggestions_paperless,
)
from app.services.pipeline.worker_suggestion_tasks import (
    process_suggestions_vision as _service_process_suggestions_vision,
)
from app.services.runtime.logging_setup import (
    bind_log_context,
    configure_logging,
    log_event,
    reset_log_context,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
HEARTBEAT_INTERVAL_SECONDS = 5
VISION_OCR_BATCH_DEFAULT = 25


def _safe_rollback(db: Session, *, context: str = "") -> None:
    try:
        db.rollback()
    except SQLAlchemyError:
        if context:
            logger.debug("DB rollback failed context=%s", context, exc_info=True)


def _page_text_value(page: object) -> str:
    clean_text = getattr(page, "clean_text", None)
    if isinstance(clean_text, str) and clean_text.strip():
        return clean_text
    raw_text = getattr(page, "text", None)
    if isinstance(raw_text, str):
        return clean_ocr_text(raw_text)
    return ""


def _vision_ocr_batch_size(
    *,
    total_pages: int,
    configured_batch_size: int,
) -> int:
    # Large runs checkpoint more frequently and reduce rework on retries.
    if total_pages >= 300:
        return min(configured_batch_size, 5)
    if total_pages >= 120:
        return min(configured_batch_size, 10)
    return configured_batch_size


def _embedding_checkpoint_batch_size(
    *,
    total_chunks: int,
    configured_batch_size: int,
) -> int:
    # Very large chunk sets use smaller batches to report progress more often.
    if total_chunks >= 1200:
        return min(configured_batch_size, 4)
    if total_chunks >= 600:
        return min(configured_batch_size, 6)
    if total_chunks >= 250:
        return min(configured_batch_size, 8)
    return configured_batch_size


def _is_large_doc(settings, doc: Document) -> bool:
    return is_large_document(
        page_count=doc.page_count,
        total_text=doc.content,
        threshold_pages=settings.large_doc_page_threshold,
    )


def _ensure_paperless_page_texts(settings, db: Session, doc: Document) -> None:
    baseline_pages = get_baseline_page_texts(
        settings,
        doc.content,
        fetch_pdf_bytes=lambda: fetch_pdf_bytes_for_doc(settings, doc),
    )
    if baseline_pages:
        upsert_page_texts(
            db,
            settings,
            doc.id,
            baseline_pages,
            source_filter="paperless_ocr",
            replace_pages=[page.page for page in baseline_pages],
        )


def _embed_with_pages(
    settings,
    db: Session,
    doc: Document,
    baseline_pages,
    vision_pages,
    embedding_source: str,
    run_id: int | None = None,
) -> None:
    _service_embed_with_pages(
        settings,
        db,
        doc,
        baseline_pages,
        vision_pages,
        embedding_source,
        run_id=run_id,
    )


def _process_sync_only(settings, db: Session, doc_id: int) -> None:
    _service_process_sync_only(
        settings,
        db,
        doc_id,
        is_cancel_requested_fn=is_cancel_requested,
    )


def _process_doc(settings, db: Session, doc_id: int, run_id: int | None = None) -> None:
    if is_cancel_requested(settings):
        logger.info("Worker cancel requested; abort doc=%s", doc_id)
        return
    _process_sync_only(settings, db, doc_id)
    raw = paperless.get_document(settings, doc_id)

    doc = get_document_or_none(db, doc_id)
    if not doc:
        return
    _process_evidence_index(settings, db, doc_id, run_id=run_id)
    ensure_document_ocr_score(settings, db, doc, "paperless_ocr")

    # Embeddings (with vision OCR)
    baseline_pages, vision_pages, _ = collect_page_texts(
        settings,
        db,
        doc,
        force_vision=True,
    )
    if vision_pages:
        ensure_document_ocr_score(settings, db, doc, "vision_ocr")
    _embed_with_pages(
        settings,
        db,
        doc,
        baseline_pages,
        vision_pages,
        "vision" if vision_pages else "paperless",
        run_id=run_id,
    )

    if _is_large_doc(settings, doc):
        _process_page_notes(settings, db, doc_id, source="paperless_ocr", run_id=run_id)
        if vision_pages:
            _process_page_notes(settings, db, doc_id, source="vision_ocr", run_id=run_id)
            _process_summary_hierarchical(settings, db, doc_id, source="vision_ocr", run_id=run_id)
        else:
            _process_summary_hierarchical(
                settings, db, doc_id, source="paperless_ocr", run_id=run_id
            )

    # Suggestions
    tags = get_cached_tags(settings)
    correspondents = get_cached_correspondents(settings)
    baseline_text = doc.content or ""
    if _is_large_doc(settings, doc):
        distilled = _service_build_distilled_context_from_hier_summary(
            db,
            doc_id=doc_id,
            source="paperless_ocr",
            max_chars=settings.worker_suggestions_max_chars,
        )
        if not distilled:
            distilled = _service_build_distilled_context_from_page_notes(
                db,
                doc_id=doc_id,
                source="paperless_ocr",
                max_chars=settings.worker_suggestions_max_chars,
            )
        if distilled:
            baseline_text = distilled
    baseline_suggestions = generate_normalized_suggestions(
        settings,
        raw,
        baseline_text,
        tags=tags,
        correspondents=correspondents,
    )
    persist_suggestions(
        db,
        doc_id,
        "paperless_ocr",
        baseline_suggestions,
        model_name=settings.text_model,
    )
    if vision_pages:
        vision_text = ""
        if _is_large_doc(settings, doc):
            vision_text = _service_build_distilled_context_from_hier_summary(
                db,
                doc_id=doc_id,
                source="vision_ocr",
                max_chars=settings.worker_suggestions_max_chars,
            )
        if not vision_text:
            vision_text = _service_build_distilled_context_from_page_notes(
                db,
                doc_id=doc_id,
                source="vision_ocr",
                max_chars=settings.worker_suggestions_max_chars,
            )
        if not vision_text:
            vision_text = _service_join_page_texts_limited(
                vision_pages,
                max_chars=settings.worker_suggestions_max_chars,
            )
        vision_suggestions = generate_normalized_suggestions(
            settings,
            raw,
            vision_text,
            tags=tags,
            correspondents=correspondents,
        )
        persist_suggestions(
            db,
            doc_id,
            "vision_ocr",
            vision_suggestions,
            model_name=settings.text_model,
        )


def _process_vision_ocr_only(
    settings, db: Session, doc_id: int, force: bool = False, run_id: int | None = None
) -> None:
    if is_cancel_requested(settings):
        logger.info("Worker cancel requested; abort vision OCR doc=%s", doc_id)
        return
    doc = get_document_or_none(db, doc_id)
    if not doc:
        return
    if not settings.enable_vision_ocr:
        logger.info("Vision OCR disabled; skipping doc=%s", doc_id)
        return
    if not settings.vision_model:
        logger.warning("VISION_MODEL not set; skipping vision OCR doc=%s", doc_id)
        return

    existing_pages = {
        int(row.page)
        for row in db.query(DocumentPageText.page)
        .filter(DocumentPageText.doc_id == doc_id, DocumentPageText.source == "vision_ocr")
        .all()
    }
    expected_pages = int(doc.page_count or 0)
    if expected_pages > 0:
        if force:
            target_pages = list(range(1, expected_pages + 1))
        else:
            target_pages = [
                page for page in range(1, expected_pages + 1) if page not in existing_pages
            ]
            if not target_pages:
                ensure_document_ocr_score(settings, db, doc, "vision_ocr")
                logger.info(
                    "Vision OCR skipped (already complete) doc=%s pages=%s", doc_id, expected_pages
                )
                return
    else:
        if not force and existing_pages:
            ensure_document_ocr_score(settings, db, doc, "vision_ocr")
            logger.info("Vision OCR skipped (cached; unknown page_count) doc=%s", doc_id)
            return
        target_pages = None

    pdf_bytes = fetch_pdf_bytes_for_doc(settings, doc)
    configured_batch_size = max(1, int(settings.vision_ocr_batch_pages or VISION_OCR_BATCH_DEFAULT))
    if settings.vision_ocr_max_pages > 0:
        batch_size = min(configured_batch_size, settings.vision_ocr_max_pages)
    else:
        batch_size = configured_batch_size

    total_pages = len(target_pages) if target_pages is not None else int(doc.page_count or 0)
    batch_size = _vision_ocr_batch_size(
        total_pages=max(0, int(total_pages)),
        configured_batch_size=max(1, int(batch_size)),
    )
    logger.info(
        "Vision OCR start doc=%s expected_pages=%s existing_pages=%s remaining=%s batch_size=%s force=%s",
        doc_id,
        doc.page_count,
        len(existing_pages),
        total_pages if total_pages > 0 else "unknown",
        batch_size,
        force,
    )

    processed_any = False
    if target_pages is None:
        _set_task_checkpoint(
            db, run_id=run_id, stage="vision_ocr", current=0, total=0, extra={"mode": "all"}
        )
        generated = vision_ocr.ocr_pdf_pages(
            settings,
            pdf_bytes,
            page_numbers=None,
        )
        if generated:
            upsert_page_texts(
                db,
                settings,
                doc_id,
                generated,
                source_filter="vision_ocr",
                replace_pages=[page.page for page in generated],
            )
            processed_any = True
    else:
        checkpoint = _get_task_run_checkpoint(db, run_id=run_id)
        resume_current = _resume_stage_current(
            checkpoint,
            stage="vision_ocr",
            total=len(target_pages),
        )
        start_index = max(0, min(resume_current, len(target_pages)))
        if start_index > 0:
            logger.info(
                "Vision OCR resume doc=%s start=%s total=%s",
                doc_id,
                start_index,
                len(target_pages),
            )
        processed = start_index
        _set_task_checkpoint(
            db,
            run_id=run_id,
            stage="vision_ocr",
            current=processed,
            total=len(target_pages),
            extra={"mode": "pages", "batch_size": batch_size, "resumed": start_index > 0},
        )
        for start in range(start_index, len(target_pages), batch_size):
            if is_cancel_requested(settings):
                logger.info(
                    "Worker cancel requested; stop vision OCR doc=%s processed=%s/%s",
                    doc_id,
                    processed,
                    len(target_pages),
                )
                break
            batch_pages = target_pages[start : start + batch_size]
            generated = vision_ocr.ocr_pdf_pages(
                settings,
                pdf_bytes,
                page_numbers=batch_pages,
            )
            if generated:
                upsert_page_texts(
                    db,
                    settings,
                    doc_id,
                    generated,
                    source_filter="vision_ocr",
                    replace_pages=[page.page for page in generated],
                )
                processed_any = True
            processed += len(batch_pages)
            logger.info(
                "Vision OCR progress doc=%s processed=%s/%s",
                doc_id,
                processed,
                len(target_pages),
            )
            _set_task_checkpoint(
                db,
                run_id=run_id,
                stage="vision_ocr",
                current=processed,
                total=len(target_pages),
                extra={"mode": "pages", "batch_size": batch_size},
            )

    if processed_any:
        ensure_document_ocr_score(settings, db, doc, "vision_ocr", force=force)


def _process_cleanup_texts(
    settings,
    db: Session,
    doc_id: int,
    *,
    source: str | None = None,
    clear_first: bool = False,
) -> None:
    if is_cancel_requested(settings):
        logger.info("Worker cancel requested; abort cleanup texts doc=%s", doc_id)
        return
    reclean_page_texts(
        db,
        settings,
        doc_id=doc_id,
        source=source,
        clear_first=clear_first,
    )


def _process_page_notes(
    settings, db: Session, doc_id: int, source: str, run_id: int | None = None
) -> None:
    if is_cancel_requested(settings):
        logger.info("Worker cancel requested; abort page notes doc=%s source=%s", doc_id, source)
        return
    doc = get_document_or_none(db, doc_id)
    if not doc:
        return
    if not _is_large_doc(settings, doc):
        logger.info(
            "Page notes skipped (small doc) doc=%s threshold=%s",
            doc_id,
            settings.large_doc_page_threshold,
        )
        return
    if source == "paperless_ocr":
        _ensure_paperless_page_texts(settings, db, doc)
    pages = (
        db.query(DocumentPageText)
        .filter(DocumentPageText.doc_id == doc_id, DocumentPageText.source == source)
        .order_by(DocumentPageText.page.asc())
        .all()
    )
    if not pages:
        logger.info("Page notes skipped (no pages) doc=%s source=%s", doc_id, source)
        return
    checkpoint = _get_task_run_checkpoint(db, run_id=run_id)
    resume_current = _resume_stage_current(
        checkpoint,
        stage="page_notes",
        source=source,
        total=len(pages),
    )
    start_index = max(0, min(resume_current, len(pages)))
    if start_index > 0:
        logger.info(
            "Page notes resume doc=%s source=%s start=%s total=%s",
            doc_id,
            source,
            start_index,
            len(pages),
        )
    _set_task_checkpoint(
        db,
        run_id=run_id,
        stage="page_notes",
        current=start_index,
        total=len(pages),
        extra={"source": source, "resumed": start_index > 0},
    )
    processed_pages = start_index
    for page in pages[start_index:]:
        if is_cancel_requested(settings):
            logger.info("Worker cancel requested; stop page notes doc=%s source=%s", doc_id, source)
            return
        text = _page_text_value(page).strip()
        if not text:
            upsert_page_note(
                db,
                doc_id=doc_id,
                page=int(page.page),
                source=source,
                payload=None,
                status="skipped",
                error="empty_page_text",
                model_name=settings.text_model,
            )
            continue
        try:
            payload = generate_page_notes(
                settings,
                page=int(page.page),
                text=text,
            )
            upsert_page_note(
                db,
                doc_id=doc_id,
                page=int(page.page),
                source=source,
                payload=payload,
                status="ok",
                model_name=settings.text_model,
            )
        except (RuntimeError, ValueError, httpx.HTTPError) as exc:
            upsert_page_note(
                db,
                doc_id=doc_id,
                page=int(page.page),
                source=source,
                payload=None,
                status="error",
                error=str(exc)[:1000],
                model_name=settings.text_model,
            )
            logger.warning(
                "Page notes failed doc=%s page=%s source=%s error=%s",
                doc_id,
                page.page,
                source,
                exc,
            )
        finally:
            processed_pages += 1
            _set_task_checkpoint(
                db,
                run_id=run_id,
                stage="page_notes",
                current=processed_pages,
                total=len(pages),
                extra={"source": source},
            )


def _process_summary_hierarchical(
    settings, db: Session, doc_id: int, source: str, run_id: int | None = None
) -> None:
    pipeline = HierarchicalSummaryPipeline(settings, db)
    pipeline.run(doc_id=doc_id, source=source, run_id=run_id)


def _process_embeddings_paperless(
    settings, db: Session, doc_id: int, run_id: int | None = None
) -> None:
    _service_process_embeddings_paperless(
        settings,
        db,
        doc_id,
        is_cancel_requested_fn=is_cancel_requested,
        run_id=run_id,
    )


def _process_evidence_index(
    settings,
    db: Session,
    doc_id: int,
    *,
    source: str = "paperless_pdf",
    run_id: int | None = None,
) -> None:
    _service_process_evidence_index(
        settings,
        db,
        doc_id,
        source=source,
        is_cancel_requested_fn=is_cancel_requested,
        run_id=run_id,
    )


def _process_embeddings_vision(
    settings, db: Session, doc_id: int, run_id: int | None = None
) -> None:
    _service_process_embeddings_vision(
        settings,
        db,
        doc_id,
        is_cancel_requested_fn=is_cancel_requested,
        run_id=run_id,
    )


def _process_similarity_index(settings, db: Session, doc_id: int) -> None:
    _service_process_similarity_index(
        settings,
        db,
        doc_id,
        is_cancel_requested_fn=is_cancel_requested,
    )


def _process_suggestions_paperless(settings, db: Session, doc_id: int) -> None:
    _service_process_suggestions_paperless(
        settings,
        db,
        doc_id,
        is_cancel_requested_fn=is_cancel_requested,
        get_tags_fn=get_cached_tags,
        get_correspondents_fn=get_cached_correspondents,
        get_document_fn=paperless.get_document,
        generate_suggestions_fn=generate_normalized_suggestions,
        persist_suggestions_fn=persist_suggestions,
    )


def _process_suggestions_vision(settings, db: Session, doc_id: int) -> None:
    _service_process_suggestions_vision(
        settings,
        db,
        doc_id,
        is_cancel_requested_fn=is_cancel_requested,
        get_tags_fn=get_cached_tags,
        get_correspondents_fn=get_cached_correspondents,
        get_document_fn=paperless.get_document,
        generate_suggestions_fn=generate_normalized_suggestions,
        persist_suggestions_fn=persist_suggestions,
        process_vision_ocr_only_fn=_process_vision_ocr_only,
    )


def _process_suggest_field(settings, db: Session, task: dict) -> None:
    _service_process_suggest_field(
        settings,
        db,
        task,
        get_document_fn=paperless.get_document,
        get_tags_fn=get_cached_tags,
        get_correspondents_fn=get_cached_correspondents,
        generate_field_variants_fn=generate_field_variants,
        upsert_suggestion_fn=upsert_suggestion,
        audit_suggestion_run_fn=audit_suggestion_run,
    )


def _build_dispatch_handler(
    settings,
    db: Session,
    task_type: str,
    doc_id: int,
    task: dict | None,
    run_id: int | None,
):
    handlers = {
        "sync": lambda: _process_sync_only(settings, db, doc_id),
        "evidence_index": lambda: _process_evidence_index(
            settings,
            db,
            doc_id,
            source=str((task or {}).get("source") or "paperless_pdf"),
            run_id=run_id,
        ),
        "embeddings_paperless": lambda: _process_embeddings_paperless(
            settings, db, doc_id, run_id=run_id
        ),
        "embeddings_vision": lambda: _process_embeddings_vision(
            settings, db, doc_id, run_id=run_id
        ),
        "similarity_index": lambda: _process_similarity_index(settings, db, doc_id),
        "cleanup_texts": lambda: _process_cleanup_texts(
            settings,
            db,
            doc_id,
            source=str((task or {}).get("source")) if (task or {}).get("source") else None,
            clear_first=bool((task or {}).get("clear_first")),
        ),
        "page_notes_paperless": lambda: _process_page_notes(
            settings, db, doc_id, "paperless_ocr", run_id=run_id
        ),
        "page_notes_vision": lambda: _process_page_notes(
            settings, db, doc_id, "vision_ocr", run_id=run_id
        ),
        "summary_hierarchical": lambda: _process_summary_hierarchical(
            settings,
            db,
            doc_id,
            str((task or {}).get("source") or "vision_ocr"),
            run_id=run_id,
        ),
        "suggestions_paperless": lambda: _process_suggestions_paperless(settings, db, doc_id),
        "suggestions_vision": lambda: _process_suggestions_vision(settings, db, doc_id),
        "suggest_field": lambda: _process_suggest_field(settings, db, task or {}),
    }
    return handlers.get(task_type)


def main() -> None:
    settings = load_settings()
    configure_logging(settings, service="worker")
    if not settings.queue_enabled:
        raise SystemExit("QUEUE_ENABLED is not set")
    client = _get_client(settings)
    if not client:
        raise SystemExit("Redis not configured")
    worker_token = f"{socket.gethostname()}:{os.getpid()}:{int(time.time())}"
    while not acquire_worker_lock(settings, worker_token):
        log_event(
            logger,
            logging.WARNING,
            "Worker lock unavailable; retrying",
            worker_id=worker_token,
            queue=QUEUE_KEY,
            retry_after_seconds=5,
        )
        time.sleep(5)
    clear_running_task(settings)
    worker_token_ctx = bind_log_context(worker_id=worker_token, queue=QUEUE_KEY)
    log_event(logger, logging.INFO, "Worker started")
    stop_event = threading.Event()
    lock_lost = threading.Event()

    def _lock_refresher() -> None:
        while not stop_event.is_set():
            if not refresh_worker_lock(settings, worker_token):
                log_event(logger, logging.ERROR, "Worker lock refresh failed")
                lock_lost.set()
                return
            stop_event.wait(30)

    def _heartbeat_refresher() -> None:
        while not stop_event.is_set():
            try:
                mark_worker_heartbeat(settings)
            except (RedisError, RuntimeError):
                log_event(
                    logger,
                    logging.WARNING,
                    "Worker heartbeat update failed",
                    exc_info=True,
                )
            stop_event.wait(HEARTBEAT_INTERVAL_SECONDS)

    lock_refresher = threading.Thread(
        target=_lock_refresher, name="worker-lock-refresher", daemon=True
    )
    heartbeat_refresher = threading.Thread(
        target=_heartbeat_refresher,
        name="worker-heartbeat-refresher",
        daemon=True,
    )
    lock_refresher.start()
    heartbeat_refresher.start()
    try:
        while True:
            if lock_lost.is_set():
                raise SystemExit("Worker lock lost; exiting")
            if is_paused(settings):
                time.sleep(0.5)
                continue
            move_due_delayed_tasks(settings, limit=100)
            if handle_worker_cancel_request(
                settings,
                is_cancel_requested_fn=is_cancel_requested,
                clear_queue_fn=clear_queue,
                reset_stats_fn=reset_stats,
                clear_cancel_fn=clear_cancel,
                log_fn=log_event,
                logger=logger,
            ):
                time.sleep(0.5)
                continue
            item = client.blpop(QUEUE_KEY, timeout=5)
            if not item:
                time.sleep(0.5)
                continue
            _, doc_id_str = item
            parsed = parse_worker_queue_item(doc_id_str, log_fn=log_event, logger=logger)
            if parsed is None:
                continue
            doc_id = parsed["doc_id"]
            task_type = parsed["task_type"]
            task = parsed["task_payload"]
            if handle_worker_cancel_request(
                settings,
                is_cancel_requested_fn=is_cancel_requested,
                clear_queue_fn=clear_queue,
                reset_stats_fn=reset_stats,
                clear_cancel_fn=clear_cancel,
                log_fn=log_event,
                logger=logger,
            ):
                log_event(
                    logger,
                    logging.INFO,
                    "Worker cancel requested; skipping task",
                    doc_id=doc_id,
                    task=task_type,
                )
                time.sleep(0.5)
                continue
            running_task = task if isinstance(task, dict) else {"doc_id": doc_id, "task": "full"}
            set_running_task(settings, running_task)
            mark_in_progress(settings)
            run_started = time.time()
            run_id: int | None = None
            run_status = "completed"
            run_error_type: str | None = None
            run_error_message: str | None = None
            pending_retry_payload: dict | None = None
            pending_retry_delay_seconds: int | None = None
            pending_dead_letter: dict | None = None
            retry_attempt = parsed["retry_attempt"]
            task_payload = task if isinstance(task, dict) else {"doc_id": doc_id, "task": task_type}
            task_context_token = bind_log_context(
                doc_id=doc_id,
                task=task_type,
                retry_attempt=retry_attempt + 1,
            )
            try:
                with SessionLocal() as db:
                    source = task_source_from_payload(task if isinstance(task, dict) else None)
                    run_row = create_task_run(
                        db,
                        doc_id=doc_id,
                        task=task_type,
                        source=source,
                        payload=task_payload,
                        worker_id=worker_token,
                        attempt=retry_attempt + 1,
                    )
                    run_id = int(run_row.id)
                    run_context_token = bind_log_context(task_run_id=run_id, task_source=source)
                    try:
                        if retry_attempt > 0:
                            previous_checkpoint = find_latest_checkpoint(
                                db,
                                doc_id=doc_id,
                                task=task_type,
                                source=source,
                            )
                            if previous_checkpoint:
                                _set_task_checkpoint(
                                    db,
                                    run_id=run_id,
                                    stage="resume",
                                    extra={"resume_from": previous_checkpoint},
                                )
                        dispatch_worker_task(
                            settings=settings,
                            db=db,
                            task_type=task_type,
                            doc_id=doc_id,
                            task=task if isinstance(task, dict) else None,
                            run_id=run_id,
                            build_handler_fn=lambda current_task_type, current_doc_id, current_task, current_run_id: _build_dispatch_handler(
                                settings,
                                db,
                                current_task_type,
                                current_doc_id,
                                current_task if isinstance(current_task, dict) else None,
                                current_run_id,
                            ),
                            process_vision_ocr_force_fn=lambda active_settings, active_db, active_doc_id, force, active_run_id: _process_vision_ocr_only(
                                active_settings,
                                active_db,
                                active_doc_id,
                                force=force,
                                run_id=active_run_id,
                            ),
                            process_full_doc_fn=lambda active_settings, active_db, active_doc_id, active_run_id: _process_doc(
                                active_settings,
                                active_db,
                                active_doc_id,
                                run_id=active_run_id,
                            ),
                        )
                    except Exception as exc:
                        worker_error = (
                            exc
                            if isinstance(exc, WorkerError)
                            else WorkerError(
                                str(exc),
                                task=task_type,
                                attempt=retry_attempt + 1,
                                original_exception=exc,
                            )
                        )
                        _safe_rollback(db, context="dispatch_task_failed")
                        run_status = "failed"
                        run_error_type = classify_worker_error(worker_error)
                        run_error_message = worker_error.message
                        log_event(
                            logger,
                            logging.ERROR,
                            "Worker task failed",
                            error_type=run_error_type,
                            error_message=run_error_message,
                            error_class=worker_error.original_type or worker_error.__class__.__name__,
                        )
                        logger.exception("Worker failed doc=%s error=%s", doc_id, exc)
                    finally:
                        reset_log_context(run_context_token)
                        duration_ms = int(max(0.0, (time.time() - run_started) * 1000))
                        should_retry = bool(
                            run_status == "failed"
                            and run_error_type
                            and is_retryable_error_type(run_error_type)
                            and retry_attempt < settings.worker_max_retries
                            and isinstance(task_payload, dict)
                        )
                        if should_retry:
                            retry_payload = dict(task_payload)
                            retry_payload["retry_count"] = retry_attempt + 1
                            pending_retry_payload = retry_payload
                            pending_retry_delay_seconds = min(300, 5 * (2**retry_attempt))
                            run_status = "retrying"
                            log_event(
                                logger,
                                logging.WARNING,
                                "Worker task requeued",
                                max_retries=settings.worker_max_retries,
                                error_type=run_error_type,
                                retry_after_seconds=pending_retry_delay_seconds,
                            )
                        elif run_status == "failed":
                            pending_dead_letter = {
                                "task": task_payload
                                if isinstance(task_payload, dict)
                                else {"doc_id": doc_id, "task": task_type},
                                "error_type": run_error_type or "WORKER_TASK_ERROR",
                                "error_message": run_error_message or "unknown error",
                                "attempt": retry_attempt + 1,
                            }
                        if run_id is not None:
                            _safe_rollback(db, context="before_finish_task_run")
                            finish_task_run(
                                db,
                                run_id=run_id,
                                status=run_status,
                                duration_ms=duration_ms,
                                error_type=run_error_type,
                                error_message=run_error_message,
                            )
            except SQLAlchemyError as exc:
                log_event(
                    logger,
                    logging.ERROR,
                    "Worker loop task bookkeeping failed",
                    error_type=classify_worker_error(exc),
                    error_message=str(exc),
                )
                logger.exception("Worker bookkeeping failed doc=%s task=%s", doc_id, task_type)
            finally:
                reset_log_context(task_context_token)
                clear_running_task(settings)
                mark_done(settings)
                record_last_run(settings, time.time() - run_started)
                if client:
                    if isinstance(task, dict):
                        client.srem(QUEUE_SET, task_key(task))
                    else:
                        client.srem(QUEUE_SET, str(doc_id))
                if pending_retry_payload is not None:
                    enqueue_task_delayed(
                        settings, pending_retry_payload, pending_retry_delay_seconds or 5
                    )
                elif pending_dead_letter is not None:
                    add_dead_letter(
                        settings,
                        task=pending_dead_letter["task"],
                        error_type=str(pending_dead_letter["error_type"]),
                        error_message=str(pending_dead_letter["error_message"]),
                        attempt=int(pending_dead_letter["attempt"]),
                    )
    finally:
        stop_event.set()
        clear_running_task(settings)
        release_worker_lock(settings, worker_token)
        reset_log_context(worker_token_ctx)

if __name__ == "__main__":
    main()





