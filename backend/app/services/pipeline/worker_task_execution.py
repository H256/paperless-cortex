from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, TypedDict

from sqlalchemy.exc import SQLAlchemyError

from app.exceptions import WorkerError
from app.services.pipeline.error_types import (
    classify_worker_error,
    is_retryable_error_type,
    task_source_from_payload,
)
from app.services.pipeline.task_runs import (
    create_task_run,
    find_latest_checkpoint,
    finish_task_run,
)
from app.services.runtime.logging_setup import bind_log_context, log_event, reset_log_context

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.orm import Session

    from app.config import Settings


class WorkerTaskExecutionResult(TypedDict):
    pending_retry_payload: dict[str, object] | None
    pending_retry_delay_seconds: int | None
    pending_dead_letter: dict[str, object] | None


def safe_rollback(db: Session, *, logger: logging.Logger, context: str = "") -> None:
    try:
        db.rollback()
    except SQLAlchemyError:
        if context:
            logger.debug("DB rollback failed context=%s", context, exc_info=True)


def execute_worker_task(
    *,
    settings: Settings,
    db: Session,
    worker_token: str,
    doc_id: int,
    task_type: str,
    task: dict[str, object] | None,
    retry_attempt: int,
    dispatch_worker_task_fn: Callable[..., None],
    build_handler_fn: Callable[[str, int, dict[str, object] | None, int | None], Callable[[], None] | None],
    process_vision_ocr_force_fn: Callable[..., None],
    process_full_doc_fn: Callable[..., None],
    set_task_checkpoint_fn: Callable[..., None],
    logger: logging.Logger,
) -> WorkerTaskExecutionResult:
    run_started = time.time()
    run_id: int | None = None
    run_status = "completed"
    run_error_type: str | None = None
    run_error_message: str | None = None
    pending_retry_payload: dict[str, object] | None = None
    pending_retry_delay_seconds: int | None = None
    pending_dead_letter: dict[str, object] | None = None
    task_payload = task if isinstance(task, dict) else {"doc_id": doc_id, "task": task_type}
    task_context_token = bind_log_context(
        doc_id=doc_id,
        task=task_type,
        retry_attempt=retry_attempt + 1,
    )
    try:
        source = task_source_from_payload(task)
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
                    set_task_checkpoint_fn(
                        db,
                        run_id=run_id,
                        stage="resume",
                        extra={"resume_from": previous_checkpoint},
                    )
            dispatch_worker_task_fn(
                settings=settings,
                db=db,
                task_type=task_type,
                doc_id=doc_id,
                task=task,
                run_id=run_id,
                build_handler_fn=build_handler_fn,
                process_vision_ocr_force_fn=process_vision_ocr_force_fn,
                process_full_doc_fn=process_full_doc_fn,
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
            safe_rollback(db, logger=logger, context="dispatch_task_failed")
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
                    "task": task_payload,
                    "error_type": run_error_type or "WORKER_TASK_ERROR",
                    "error_message": run_error_message or "unknown error",
                    "attempt": retry_attempt + 1,
                }
            if run_id is not None:
                safe_rollback(db, logger=logger, context="before_finish_task_run")
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
    return {
        "pending_retry_payload": pending_retry_payload,
        "pending_retry_delay_seconds": pending_retry_delay_seconds,
        "pending_dead_letter": pending_dead_letter,
    }
