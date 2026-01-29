from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.config import Settings, load_settings
from app.services.queue import enqueue_docs, queue_stats, peek_queue, cancel_queue, reset_stats

router = APIRouter(prefix="/queue", tags=["queue"])


def settings_dep() -> Settings:
    return load_settings()


class QueueEnqueue(BaseModel):
    doc_ids: list[int]


@router.get("/status")
def get_queue_status(settings: Settings = Depends(settings_dep)):
    if not settings.queue_enabled:
        return {"enabled": False, "length": None}
    stats = queue_stats(settings) or {"length": None, "total": 0, "in_progress": 0, "done": 0}
    return {"enabled": True, **stats}


@router.post("/enqueue")
def enqueue(payload: QueueEnqueue, settings: Settings = Depends(settings_dep)):
    if not settings.queue_enabled:
        return {"enabled": False, "enqueued": 0}
    count = enqueue_docs(settings, payload.doc_ids)
    return {"enabled": True, "enqueued": count}


@router.get("/peek")
def peek(limit: int = 20, settings: Settings = Depends(settings_dep)):
    if not settings.queue_enabled:
        return {"enabled": False, "items": []}
    items = peek_queue(settings, limit=limit)
    return {"enabled": True, "items": items}


@router.post("/clear")
def clear(settings: Settings = Depends(settings_dep)):
    if not settings.queue_enabled:
        return {"enabled": False}
    cancel_queue(settings)
    return {"enabled": True, "cancelled": True}


@router.post("/cancel")
def cancel(settings: Settings = Depends(settings_dep)):
    if not settings.queue_enabled:
        return {"enabled": False}
    cancel_queue(settings)
    return {"enabled": True, "cancelled": True}


@router.post("/reset-stats")
def reset(settings: Settings = Depends(settings_dep)):
    if not settings.queue_enabled:
        return {"enabled": False}
    reset_stats(settings)
    return {"enabled": True}
