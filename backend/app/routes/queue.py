from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ValidationError

from app.api_models import (
    ErrorTypeCatalogResponse,
    QueueCancelResponse,
    QueueDelayedResponse,
    QueueDlqActionResponse,
    QueueDlqResponse,
    QueueEnqueueResponse,
    QueueMoveResponse,
    QueuePauseResponse,
    QueuePeekResponse,
    QueueRemoveResponse,
    QueueResetResponse,
    QueueRunningResponse,
    QueueStatusResponse,
    QueueWorkerLockResetResponse,
    QueueWorkerLockStatusResponse,
    TaskRunItem,
    TaskRunListResponse,
)
from app.db import get_db
from app.deps import get_settings
from app.services.pipeline.error_types import get_error_type_details, list_error_type_details
from app.services.pipeline.queue import (
    cancel_queue,
    clear_dead_letters,
    enqueue_docs,
    get_running_task,
    is_paused,
    move_queue_item_to_bottom,
    move_queue_item_to_top,
    pause_queue,
    peek_dead_letters,
    peek_delayed_queue,
    peek_queue,
    queue_stats,
    remove_queue_item,
    reorder_queue,
    requeue_dead_letter_item,
    reset_stats,
    reset_worker_lock,
    resume_queue,
    worker_lock_status,
)
from app.services.pipeline.queue_responses import queue_disabled_response
from app.services.pipeline.task_runs import list_task_runs

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.config import Settings

router = APIRouter(prefix="/queue", tags=["queue"])
logger = logging.getLogger(__name__)


class QueueEnqueue(BaseModel):
    doc_ids: list[int]


class QueueMoveRequest(BaseModel):
    from_index: int
    to_index: int


class QueueRemoveRequest(BaseModel):
    index: int


class QueueMoveEdgeRequest(BaseModel):
    index: int


class QueueDlqRequeueRequest(BaseModel):
    index: int


def _parse_json_object(raw: str | None) -> dict | None:
    if not raw:
        return None
    payload = str(raw).strip()
    if not payload.startswith(("{", "[")):
        return None
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, dict):
        return parsed
    return None


@router.get("/status", response_model=QueueStatusResponse)
def get_queue_status(settings: Settings = Depends(get_settings)) -> dict[str, object]:
    """Return queue length/progress plus paused state for the active worker queue."""
    if not settings.queue_enabled:
        return queue_disabled_response(length=None, paused=False)
    stats = queue_stats(settings) or {"length": 0, "total": 0, "in_progress": 0, "done": 0}
    return {"enabled": True, **stats, "paused": is_paused(settings)}


@router.post("/enqueue", response_model=QueueEnqueueResponse)
def enqueue(payload: QueueEnqueue, settings: Settings = Depends(get_settings)) -> dict[str, object]:
    """Enqueue one or more document IDs for default worker processing."""
    if not settings.queue_enabled:
        return queue_disabled_response(enqueued=0)
    count = enqueue_docs(settings, payload.doc_ids)
    return {"enabled": True, "enqueued": count}


@router.get("/peek", response_model=QueuePeekResponse)
def peek(limit: int = 20, settings: Settings = Depends(get_settings)) -> dict[str, object]:
    """Preview queued work items without removing them from the queue."""
    if not settings.queue_enabled:
        return queue_disabled_response(items=[])
    items = peek_queue(settings, limit=limit)
    return {"enabled": True, "items": items}


@router.post("/clear", response_model=QueueCancelResponse)
def clear(settings: Settings = Depends(get_settings)) -> dict[str, object]:
    """Clear the active queue by reusing the queue-cancel path."""
    if not settings.queue_enabled:
        return queue_disabled_response()
    cancel_queue(settings)
    return {"enabled": True, "cancelled": True}


@router.post("/cancel", response_model=QueueCancelResponse)
def cancel(settings: Settings = Depends(get_settings)) -> dict[str, object]:
    """Request queue cancellation for the current worker run."""
    if not settings.queue_enabled:
        return queue_disabled_response()
    cancel_queue(settings)
    return {"enabled": True, "cancelled": True}


@router.post("/reset-stats", response_model=QueueResetResponse)
def reset(settings: Settings = Depends(get_settings)) -> dict[str, object]:
    """Reset persisted queue counters without modifying queued items."""
    if not settings.queue_enabled:
        return queue_disabled_response()
    reset_stats(settings)
    return {"enabled": True}


@router.post("/pause", response_model=QueuePauseResponse)
def pause(settings: Settings = Depends(get_settings)) -> dict[str, object]:
    """Pause queue consumption while keeping queued items intact."""
    if not settings.queue_enabled:
        return queue_disabled_response(paused=False)
    pause_queue(settings)
    return {"enabled": True, "paused": True}


@router.post("/resume", response_model=QueuePauseResponse)
def resume(settings: Settings = Depends(get_settings)) -> dict[str, object]:
    """Resume queue consumption after a pause."""
    if not settings.queue_enabled:
        return queue_disabled_response(paused=False)
    resume_queue(settings)
    return {"enabled": True, "paused": False}


@router.post("/reorder", response_model=QueueMoveResponse)
def move(payload: QueueMoveRequest, settings: Settings = Depends(get_settings)) -> dict[str, object]:
    """Move a queue item from one index to another."""
    if not settings.queue_enabled:
        return queue_disabled_response(moved=False)
    moved = reorder_queue(settings, payload.from_index, payload.to_index)
    return {"enabled": True, "moved": moved}


@router.post("/move-top", response_model=QueueMoveResponse)
def move_top(
    payload: QueueMoveEdgeRequest, settings: Settings = Depends(get_settings)
) -> dict[str, object]:
    """Move a queue item to the front of the queue."""
    if not settings.queue_enabled:
        return queue_disabled_response(moved=False)
    moved = move_queue_item_to_top(settings, payload.index)
    return {"enabled": True, "moved": moved}


@router.post("/move-bottom", response_model=QueueMoveResponse)
def move_bottom(
    payload: QueueMoveEdgeRequest, settings: Settings = Depends(get_settings)
) -> dict[str, object]:
    """Move a queue item to the end of the queue."""
    if not settings.queue_enabled:
        return queue_disabled_response(moved=False)
    moved = move_queue_item_to_bottom(settings, payload.index)
    return {"enabled": True, "moved": moved}


@router.post("/remove", response_model=QueueRemoveResponse)
def remove(payload: QueueRemoveRequest, settings: Settings = Depends(get_settings)) -> dict[str, object]:
    """Remove one queue item by index."""
    if not settings.queue_enabled:
        return queue_disabled_response(removed=False)
    removed = remove_queue_item(settings, payload.index)
    return {"enabled": True, "removed": removed}


@router.get("/worker-lock", response_model=QueueWorkerLockStatusResponse)
def get_worker_lock(settings: Settings = Depends(get_settings)) -> dict[str, object]:
    """Report worker-lock ownership and TTL details for queue debugging."""
    if not settings.queue_enabled:
        return queue_disabled_response(has_lock=False, owner=None, ttl_seconds=None)
    return {"enabled": True, **worker_lock_status(settings)}


@router.get("/running", response_model=QueueRunningResponse)
def get_running(settings: Settings = Depends(get_settings)) -> dict[str, object]:
    """Return the task the worker currently marks as running, if any."""
    if not settings.queue_enabled:
        return queue_disabled_response(task=None, started_at=None)
    return {"enabled": True, **get_running_task(settings)}


@router.post("/worker-lock/reset", response_model=QueueWorkerLockResetResponse)
def reset_worker_lock_route(
    force: bool = False, settings: Settings = Depends(get_settings)
) -> dict[str, object]:
    """Reset the worker lock for recovery scenarios, optionally forcing the reset."""
    if not settings.queue_enabled:
        return queue_disabled_response(reset=False, had_lock=False, reason="queue_disabled")
    result = reset_worker_lock(settings, force=force)
    return {"enabled": True, **result}


@router.get("/dlq", response_model=QueueDlqResponse)
def get_dlq(limit: int = 100, settings: Settings = Depends(get_settings)) -> dict[str, object]:
    """List dead-letter queue items for inspection and recovery."""
    if not settings.queue_enabled:
        return {"enabled": False, "items": []}
    items = peek_dead_letters(settings, limit=limit)
    return {"enabled": True, "items": items}


@router.get("/delayed", response_model=QueueDelayedResponse)
def get_delayed_queue(
    limit: int = 100, settings: Settings = Depends(get_settings)
) -> dict[str, object]:
    """List delayed queue items that are waiting for their retry time."""
    if not settings.queue_enabled:
        return {"enabled": False, "items": []}
    items = peek_delayed_queue(settings, limit=limit)
    return {"enabled": True, "items": items}


@router.post("/dlq/clear", response_model=QueueDlqActionResponse)
def clear_dlq(settings: Settings = Depends(get_settings)) -> dict[str, object]:
    """Clear all dead-letter queue items."""
    if not settings.queue_enabled:
        return {"enabled": False, "ok": False}
    clear_dead_letters(settings)
    return {"enabled": True, "ok": True}


@router.post("/dlq/requeue", response_model=QueueDlqActionResponse)
def requeue_dlq(
    payload: QueueDlqRequeueRequest, settings: Settings = Depends(get_settings)
) -> dict[str, object]:
    """Move one dead-letter queue item back into the active queue."""
    if not settings.queue_enabled:
        return {"enabled": False, "ok": False}
    ok = requeue_dead_letter_item(settings, payload.index)
    return {"enabled": True, "ok": bool(ok)}


@router.get("/task-runs", response_model=TaskRunListResponse)
def get_task_runs(
    doc_id: int | None = None,
    task: str | None = None,
    status: str | None = None,
    error_type: str | None = None,
    q: str | None = None,
    limit: int = 100,
    offset: int = 0,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """List persisted worker task runs with filters for queue/ops inspection."""
    if not settings.queue_enabled:
        return {"enabled": False, "count": 0, "items": []}
    total, rows = list_task_runs(
        db,
        doc_id=doc_id,
        task=task,
        status=status,
        error_type=error_type,
        query_text=q,
        limit=limit,
        offset=offset,
    )
    items: list[TaskRunItem] = []
    for row in rows:
        try:
            error_details = get_error_type_details(row.error_type)
            items.append(
                TaskRunItem(
                    id=int(row.id),
                    doc_id=int(row.doc_id) if row.doc_id is not None else None,
                    task=str(row.task),
                    source=row.source,
                    status=str(row.status),
                    worker_id=row.worker_id,
                    attempt=int(row.attempt or 1),
                    checkpoint=_parse_json_object(row.checkpoint_json),
                    error_type=row.error_type,
                    error_retryable=error_details.get("retryable") if error_details else None,
                    error_category=error_details.get("category") if error_details else None,
                    error_message=row.error_message,
                    started_at=row.started_at,
                    finished_at=row.finished_at,
                    duration_ms=int(row.duration_ms) if row.duration_ms is not None else None,
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                )
            )
        except (AttributeError, TypeError, ValidationError, ValueError):
            logger.exception(
                "Failed to serialize task-run row id=%s doc_id=%s task=%s",
                getattr(row, "id", None),
                getattr(row, "doc_id", None),
                getattr(row, "task", None),
            )
    return {"enabled": True, "count": total, "items": items}


@router.get("/error-types", response_model=ErrorTypeCatalogResponse)
def get_error_types(settings: Settings = Depends(get_settings)) -> dict[str, object]:
    """Return the stable worker error-type catalog exposed to the UI."""
    if not settings.queue_enabled:
        return {"enabled": False, "items": []}
    return {"enabled": True, "items": list_error_type_details()}
