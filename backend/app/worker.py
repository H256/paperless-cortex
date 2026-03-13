from __future__ import annotations

import logging
import os
import socket
import time
from typing import TYPE_CHECKING

from sqlalchemy.exc import SQLAlchemyError

from app.config import load_settings
from app.db import SessionLocal
from app.exceptions import WorkerError
from app.services.ai.hierarchical_summary import is_large_document
from app.services.ai.ocr_scoring import ensure_document_ocr_score
from app.services.ai.suggestion_store import (
    audit_suggestion_run,
    persist_suggestions,
    upsert_suggestion,
)
from app.services.ai.suggestions import generate_field_variants, generate_normalized_suggestions
from app.services.documents.documents import get_document_or_none
from app.services.documents.page_text_store import reclean_page_texts
from app.services.documents.page_texts_merge import collect_page_texts
from app.services.integrations import paperless
from app.services.integrations.meta_cache import get_cached_correspondents, get_cached_tags
from app.services.pipeline.error_types import (
    classify_worker_error,
    is_retryable_error_type,
    task_source_from_payload,
)
from app.services.pipeline.queue import (
    QUEUE_KEY,
    clear_cancel,
    clear_queue,
    is_cancel_requested,
    is_paused,
    reset_stats,
)
from app.services.pipeline.task_runs import (
    create_task_run,
    find_latest_checkpoint,
    finish_task_run,
)
from app.services.pipeline.worker_checkpoint import set_task_checkpoint as _set_task_checkpoint
from app.services.pipeline.worker_content_tasks import (
    process_page_notes as _service_process_page_notes,
)
from app.services.pipeline.worker_content_tasks import (
    process_summary_hierarchical as _service_process_summary_hierarchical,
)
from app.services.pipeline.worker_content_tasks import (
    process_vision_ocr_only as _service_process_vision_ocr_only,
)
from app.services.pipeline.worker_dispatch import (
    build_dispatch_handler as _service_build_dispatch_handler,
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
from app.services.pipeline.worker_orchestration import (
    process_full_document as _service_process_full_document,
)
from app.services.pipeline.worker_queue_runtime import (
    acquire_worker_runtime,
    finalize_worker_task,
    mark_worker_task_start,
    run_worker_queue_maintenance,
    shutdown_worker_runtime,
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

    from app.models import Document

logger = logging.getLogger(__name__)
HEARTBEAT_INTERVAL_SECONDS = 5


def _safe_rollback(db: Session, *, context: str = "") -> None:
    try:
        db.rollback()
    except SQLAlchemyError:
        if context:
            logger.debug("DB rollback failed context=%s", context, exc_info=True)


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
    _service_process_full_document(
        settings,
        db,
        doc_id,
        run_id=run_id,
        is_cancel_requested_fn=is_cancel_requested,
        process_sync_only_fn=_process_sync_only,
        get_document_fn=paperless.get_document,
        get_local_document_fn=get_document_or_none,
        process_evidence_index_fn=_process_evidence_index,
        ensure_ocr_score_fn=ensure_document_ocr_score,
        collect_page_texts_fn=collect_page_texts,
        embed_with_pages_fn=_embed_with_pages,
        is_large_doc_fn=_is_large_doc,
        process_page_notes_fn=_process_page_notes,
        process_summary_hierarchical_fn=_process_summary_hierarchical,
        get_tags_fn=get_cached_tags,
        get_correspondents_fn=get_cached_correspondents,
        build_hier_summary_fn=_service_build_distilled_context_from_hier_summary,
        build_page_notes_fn=_service_build_distilled_context_from_page_notes,
        join_pages_fn=_service_join_page_texts_limited,
        generate_suggestions_fn=generate_normalized_suggestions,
        persist_suggestions_fn=persist_suggestions,
    )


def _process_vision_ocr_only(
    settings, db: Session, doc_id: int, force: bool = False, run_id: int | None = None
) -> None:
    _service_process_vision_ocr_only(
        settings,
        db,
        doc_id,
        force=force,
        run_id=run_id,
        is_cancel_requested_fn=is_cancel_requested,
    )


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
    _service_process_page_notes(
        settings,
        db,
        doc_id,
        source,
        run_id=run_id,
        is_cancel_requested_fn=is_cancel_requested,
    )


def _process_summary_hierarchical(
    settings, db: Session, doc_id: int, source: str, run_id: int | None = None
) -> None:
    _service_process_summary_hierarchical(
        settings,
        db,
        doc_id,
        source,
        run_id=run_id,
    )


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
    return _service_build_dispatch_handler(
        settings=settings,
        db=db,
        task_type=task_type,
        doc_id=doc_id,
        task=task,
        run_id=run_id,
        process_sync_only_fn=_process_sync_only,
        process_evidence_index_fn=_process_evidence_index,
        process_embeddings_paperless_fn=_process_embeddings_paperless,
        process_embeddings_vision_fn=_process_embeddings_vision,
        process_similarity_index_fn=_process_similarity_index,
        process_cleanup_texts_fn=_process_cleanup_texts,
        process_page_notes_fn=_process_page_notes,
        process_summary_hierarchical_fn=_process_summary_hierarchical,
        process_suggestions_paperless_fn=_process_suggestions_paperless,
        process_suggestions_vision_fn=_process_suggestions_vision,
        process_suggest_field_fn=_process_suggest_field,
    )


def main() -> None:
    settings = load_settings()
    configure_logging(settings, service="worker")
    if not settings.queue_enabled:
        raise SystemExit("QUEUE_ENABLED is not set")
    worker_token = f"{socket.gethostname()}:{os.getpid()}:{int(time.time())}"
    client, worker_token_ctx, stop_event, lock_lost = acquire_worker_runtime(
        settings,
        worker_token=worker_token,
        heartbeat_interval_seconds=HEARTBEAT_INTERVAL_SECONDS,
        logger=logger,
    )
    try:
        while True:
            if lock_lost.is_set():
                raise SystemExit("Worker lock lost; exiting")
            if is_paused(settings):
                time.sleep(0.5)
                continue
            run_worker_queue_maintenance(settings)
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
            mark_worker_task_start(settings, running_task)
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
                        if run_error_type == "VECTOR_CHUNKS_MISSING":
                            logger.warning("Worker failed doc=%s error=%s", doc_id, exc)
                        else:
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
                finalize_worker_task(
                    settings,
                    client=client,
                    task=task if isinstance(task, dict) else None,
                    doc_id=doc_id,
                    run_started=run_started,
                    pending_retry_payload=pending_retry_payload,
                    pending_retry_delay_seconds=pending_retry_delay_seconds,
                    pending_dead_letter=pending_dead_letter,
                )
    finally:
        stop_event.set()
        shutdown_worker_runtime(settings, worker_token=worker_token, worker_token_ctx=worker_token_ctx)

if __name__ == "__main__":
    main()





