from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING, Any

from redis.exceptions import RedisError

from app.services.pipeline.queue import (
    QUEUE_KEY,
    QUEUE_SET,
    _get_client,
    acquire_worker_lock,
    add_dead_letter,
    clear_running_task,
    enqueue_task_delayed,
    mark_done,
    mark_in_progress,
    mark_worker_heartbeat,
    move_due_delayed_tasks,
    record_last_run,
    refresh_worker_lock,
    release_worker_lock,
    set_running_task,
    task_key,
)
from app.services.runtime.logging_setup import bind_log_context, log_event, reset_log_context

if TYPE_CHECKING:
    from app.config import Settings


def require_worker_client(settings: Settings) -> Any:
    client = _get_client(settings)
    if not client:
        raise SystemExit("Redis not configured")
    return client


def acquire_worker_runtime(
    settings: Settings,
    *,
    worker_token: str,
    heartbeat_interval_seconds: int,
    logger: logging.Logger,
) -> tuple[Any, Any, threading.Event, threading.Event]:
    client = require_worker_client(settings)
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
            stop_event.wait(heartbeat_interval_seconds)

    threading.Thread(
        target=_lock_refresher, name="worker-lock-refresher", daemon=True
    ).start()
    threading.Thread(
        target=_heartbeat_refresher,
        name="worker-heartbeat-refresher",
        daemon=True,
    ).start()
    return client, worker_token_ctx, stop_event, lock_lost


def run_worker_queue_maintenance(settings: Settings) -> None:
    move_due_delayed_tasks(settings, limit=100)


def mark_worker_task_start(settings: Settings, running_task: dict[str, object]) -> None:
    set_running_task(settings, running_task)
    mark_in_progress(settings)


def finalize_worker_task(
    settings: Settings,
    *,
    client: Any,
    task: dict[str, object] | None,
    doc_id: int,
    run_started: float,
    pending_retry_payload: dict[str, object] | None,
    pending_retry_delay_seconds: int | None,
    pending_dead_letter: dict[str, object] | None,
) -> None:
    clear_running_task(settings)
    mark_done(settings)
    record_last_run(settings, time.time() - run_started)
    if isinstance(task, dict):
        client.srem(QUEUE_SET, task_key(task))
    else:
        client.srem(QUEUE_SET, str(doc_id))
    if pending_retry_payload is not None:
        enqueue_task_delayed(settings, pending_retry_payload, pending_retry_delay_seconds or 5)
    elif pending_dead_letter is not None:
        dead_letter_task = pending_dead_letter["task"]
        add_dead_letter(
            settings,
            task=dead_letter_task if isinstance(dead_letter_task, dict) else {"doc_id": doc_id},
            error_type=str(pending_dead_letter["error_type"]),
            error_message=str(pending_dead_letter["error_message"]),
            attempt=int(str(pending_dead_letter["attempt"])),
        )


def shutdown_worker_runtime(settings: Settings, *, worker_token: str, worker_token_ctx: Any) -> None:
    clear_running_task(settings)
    release_worker_lock(settings, worker_token)
    reset_log_context(worker_token_ctx)
