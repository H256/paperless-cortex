from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.config import Settings
from app.deps import get_settings
from app.services.queue import (
    enqueue_docs,
    queue_stats,
    peek_queue,
    cancel_queue,
    reset_stats,
    pause_queue,
    resume_queue,
    is_paused,
    reorder_queue,
    move_queue_item_to_top,
    move_queue_item_to_bottom,
    remove_queue_item,
)
from app.api_models import (
    QueueStatusResponse,
    QueueEnqueueResponse,
    QueuePeekResponse,
    QueueCancelResponse,
    QueueResetResponse,
    QueuePauseResponse,
    QueueMoveResponse,
    QueueRemoveResponse,
)

router = APIRouter(prefix="/queue", tags=["queue"])


class QueueEnqueue(BaseModel):
    doc_ids: list[int]


class QueueMoveRequest(BaseModel):
    from_index: int
    to_index: int


class QueueRemoveRequest(BaseModel):
    index: int


class QueueMoveEdgeRequest(BaseModel):
    index: int


@router.get("/status", response_model=QueueStatusResponse)
def get_queue_status(settings: Settings = Depends(get_settings)):
    if not settings.queue_enabled:
        return {"enabled": False, "length": None, "paused": False}
    stats = queue_stats(settings) or {"length": None, "total": 0, "in_progress": 0, "done": 0}
    return {"enabled": True, **stats, "paused": is_paused(settings)}


@router.post("/enqueue", response_model=QueueEnqueueResponse)
def enqueue(payload: QueueEnqueue, settings: Settings = Depends(get_settings)):
    if not settings.queue_enabled:
        return {"enabled": False, "enqueued": 0}
    count = enqueue_docs(settings, payload.doc_ids)
    return {"enabled": True, "enqueued": count}


@router.get("/peek", response_model=QueuePeekResponse)
def peek(limit: int = 20, settings: Settings = Depends(get_settings)):
    if not settings.queue_enabled:
        return {"enabled": False, "items": []}
    items = peek_queue(settings, limit=limit)
    return {"enabled": True, "items": items}


@router.post("/clear", response_model=QueueCancelResponse)
def clear(settings: Settings = Depends(get_settings)):
    if not settings.queue_enabled:
        return {"enabled": False}
    cancel_queue(settings)
    return {"enabled": True, "cancelled": True}


@router.post("/cancel", response_model=QueueCancelResponse)
def cancel(settings: Settings = Depends(get_settings)):
    if not settings.queue_enabled:
        return {"enabled": False}
    cancel_queue(settings)
    return {"enabled": True, "cancelled": True}


@router.post("/reset-stats", response_model=QueueResetResponse)
def reset(settings: Settings = Depends(get_settings)):
    if not settings.queue_enabled:
        return {"enabled": False}
    reset_stats(settings)
    return {"enabled": True}


@router.post("/pause", response_model=QueuePauseResponse)
def pause(settings: Settings = Depends(get_settings)):
    if not settings.queue_enabled:
        return {"enabled": False, "paused": False}
    pause_queue(settings)
    return {"enabled": True, "paused": True}


@router.post("/resume", response_model=QueuePauseResponse)
def resume(settings: Settings = Depends(get_settings)):
    if not settings.queue_enabled:
        return {"enabled": False, "paused": False}
    resume_queue(settings)
    return {"enabled": True, "paused": False}


@router.post("/reorder", response_model=QueueMoveResponse)
def move(payload: QueueMoveRequest, settings: Settings = Depends(get_settings)):
    if not settings.queue_enabled:
        return {"enabled": False, "moved": False}
    moved = reorder_queue(settings, payload.from_index, payload.to_index)
    return {"enabled": True, "moved": moved}


@router.post("/move-top", response_model=QueueMoveResponse)
def move_top(payload: QueueMoveEdgeRequest, settings: Settings = Depends(get_settings)):
    if not settings.queue_enabled:
        return {"enabled": False, "moved": False}
    moved = move_queue_item_to_top(settings, payload.index)
    return {"enabled": True, "moved": moved}


@router.post("/move-bottom", response_model=QueueMoveResponse)
def move_bottom(payload: QueueMoveEdgeRequest, settings: Settings = Depends(get_settings)):
    if not settings.queue_enabled:
        return {"enabled": False, "moved": False}
    moved = move_queue_item_to_bottom(settings, payload.index)
    return {"enabled": True, "moved": moved}


@router.post("/remove", response_model=QueueRemoveResponse)
def remove(payload: QueueRemoveRequest, settings: Settings = Depends(get_settings)):
    if not settings.queue_enabled:
        return {"enabled": False, "removed": False}
    removed = remove_queue_item(settings, payload.index)
    return {"enabled": True, "removed": removed}
