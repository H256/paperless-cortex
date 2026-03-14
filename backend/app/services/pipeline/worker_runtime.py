from __future__ import annotations

import json
import logging
from collections.abc import Callable
from json import JSONDecodeError
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class ParsedWorkerTask(TypedDict):
    doc_id: int
    task_type: str
    task_payload: dict[str, object]
    retry_attempt: int


LogFn = Callable[..., None]
DispatchHandler = Callable[[], None]
TaskHandlerFactory = Callable[[str, int, dict[str, object] | None, int | None], DispatchHandler | None]


def handle_worker_cancel_request[SettingsT](
    settings: SettingsT,
    *,
    is_cancel_requested_fn: Callable[[SettingsT], bool],
    clear_queue_fn: Callable[[SettingsT], object],
    reset_stats_fn: Callable[[SettingsT], object],
    clear_cancel_fn: Callable[[SettingsT], object],
    log_fn: LogFn,
    logger: logging.Logger,
) -> bool:
    """Honor a queued worker-cancel request by clearing the queue and resetting counters."""
    if not is_cancel_requested_fn(settings):
        return False
    log_fn(logger, logging.INFO, "Worker cancel requested; clearing queue")
    clear_queue_fn(settings)
    reset_stats_fn(settings)
    clear_cancel_fn(settings)
    return True


def parse_worker_queue_item(
    raw_item: bytes | str,
    *,
    log_fn: LogFn,
    logger: logging.Logger,
) -> ParsedWorkerTask | None:
    """Normalize raw queue payloads into the worker's typed dispatch format."""
    task: dict[str, object] | None = None
    try:
        candidate = json.loads(raw_item)
        task = candidate if isinstance(candidate, dict) else None
    except JSONDecodeError:
        task = None

    if isinstance(task, dict) and "doc_id" in task:
        raw_task_doc_id = task.get("doc_id")
        if not isinstance(raw_task_doc_id, int):
            log_fn(
                logger,
                logging.WARNING,
                "Invalid task doc_id in queue payload",
                payload=task,
            )
            return None
        retry_attempt = 0
        raw_retry_count = task.get("retry_count")
        if isinstance(raw_retry_count, int):
            retry_attempt = raw_retry_count
        elif isinstance(raw_retry_count, str):
            try:
                retry_attempt = int(raw_retry_count)
            except ValueError:
                retry_attempt = 0
        return {
            "doc_id": int(raw_task_doc_id),
            "task_type": str(task.get("task") or "full"),
            "task_payload": task,
            "retry_attempt": retry_attempt,
        }

    try:
        doc_id = int(raw_item)
    except (TypeError, ValueError):
        log_fn(
            logger,
            logging.WARNING,
            "Invalid doc_id in queue",
            payload=raw_item,
        )
        return None
    return {
        "doc_id": doc_id,
        "task_type": "full",
        "task_payload": {"doc_id": doc_id, "task": "full"},
        "retry_attempt": 0,
    }


def dispatch_worker_task(
    *,
    settings: object,
    db: Session,
    task_type: str,
    doc_id: int,
    task: dict[str, object] | None,
    run_id: int | None,
    build_handler_fn: TaskHandlerFactory,
    process_vision_ocr_force_fn: Callable[[object, Session, int, bool, int | None], None],
    process_full_doc_fn: Callable[[object, Session, int, int | None], None],
) -> None:
    """Dispatch one normalized worker task to a specific handler or the full-doc fallback."""
    if task_type == "vision_ocr":
        force = bool(task.get("force")) if isinstance(task, dict) else False
        process_vision_ocr_force_fn(settings, db, doc_id, force, run_id)
        return
    handler = build_handler_fn(task_type, doc_id, task, run_id)
    if handler is not None:
        handler()
        return
    process_full_doc_fn(settings, db, doc_id, run_id)
