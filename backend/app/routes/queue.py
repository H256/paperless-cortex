from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.config import Settings, load_settings
from app.services.queue import enqueue_docs, queue_length

router = APIRouter(prefix="/queue", tags=["queue"])


def settings_dep() -> Settings:
    return load_settings()


class QueueEnqueue(BaseModel):
    doc_ids: list[int]


@router.get("/status")
def get_queue_status(settings: Settings = Depends(settings_dep)):
    if not settings.queue_enabled:
        return {"enabled": False, "length": None}
    length = queue_length(settings)
    return {"enabled": True, "length": length}


@router.post("/enqueue")
def enqueue(payload: QueueEnqueue, settings: Settings = Depends(settings_dep)):
    if not settings.queue_enabled:
        return {"enabled": False, "enqueued": 0}
    count = enqueue_docs(settings, payload.doc_ids)
    return {"enabled": True, "enqueued": count}
