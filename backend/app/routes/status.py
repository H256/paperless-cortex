from __future__ import annotations

import asyncio
import json
import time

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import exists
from sqlalchemy.orm import Session

from app.config import Settings
from app.deps import get_settings
from app.services.queue import is_paused, queue_stats, worker_status
from app.services import paperless
from app.services import llm_client
from app.api_models import StatusResponse
from app.db import SessionLocal
from app.models import Document, DocumentEmbedding, DocumentPageText, DocumentSuggestion, SyncState
from app.services.time_utils import estimate_eta_seconds

router = APIRouter(prefix="/status", tags=["status"])


def _fetch_models(settings: Settings) -> tuple[bool, str, list[dict[str, object]]]:
    base_url = settings.llm_base_url
    if not base_url:
        return False, "LLM_BASE_URL not set", []
    try:
        with llm_client.client(settings, timeout=5) as client:
            response = client.get(
                f"{base_url.rstrip('/')}/v1/models",
                headers=llm_client.headers(settings),
            )
            response.raise_for_status()
            payload = response.json()
        models = payload.get("data") or []
        if not isinstance(models, list):
            return False, "Invalid models payload", []
        return True, "ok", [m for m in models if isinstance(m, dict)]
    except Exception as exc:
        return False, exc.__class__.__name__, []


def _model_status(models: list[dict[str, object]], model_name: str | None) -> tuple[bool, str]:
    if not model_name:
        return False, "model not set"
    for model in models:
        if model.get("id") == model_name:
            status = model.get("status") or {}
            value = status.get("value")
            if isinstance(value, str) and value:
                return value == "loaded", value
            return True, "unknown"
    return False, "not found"


def _status_payload(settings: Settings) -> dict[str, object]:
    started = time.perf_counter()
    llm_ok, llm_detail, models = _fetch_models(settings)
    text_ok, text_detail = _model_status(models, settings.text_model)
    embed_ok, embed_detail = _model_status(models, settings.embedding_model)
    vision_ok, vision_detail = _model_status(models, settings.vision_model)
    worker_ok, worker_detail = worker_status(settings) if settings.queue_enabled else (False, "Queue disabled")
    paperless_base = paperless.base_url(settings) or ""
    return {
        "web": {"status": "UP"},
        "worker": {"status": "UP" if worker_ok else "DOWN", "detail": worker_detail},
        "llm": {"status": "UP" if llm_ok else "DOWN", "detail": llm_detail},
        "llm_text": {"status": "UP" if text_ok else "DOWN", "detail": text_detail},
        "llm_embedding": {"status": "UP" if embed_ok else "DOWN", "detail": embed_detail},
        "llm_vision": {"status": "UP" if vision_ok else "DOWN", "detail": vision_detail},
        "paperless_base_url": paperless_base,
        "llm_base_url": settings.llm_base_url,
        "qdrant_url": settings.qdrant_url,
        "redis_host": settings.redis_host,
        "text_model": settings.text_model,
        "embedding_model": settings.embedding_model,
        "vision_model": settings.vision_model,
        "latency_ms": int((time.perf_counter() - started) * 1000),
    }


@router.get("", response_model=StatusResponse)
def status(settings: Settings = Depends(get_settings)):
    return _status_payload(settings)


def _sync_state_payload(db: Session, key: str) -> dict[str, object]:
    state = db.get(SyncState, key)
    if not state:
        return {"status": "idle", "processed": 0, "total": 0, "started_at": None}
    eta_seconds = estimate_eta_seconds(state.started_at, state.processed, state.total)
    return {
        "last_synced_at": state.last_synced_at,
        "status": state.status or "idle",
        "processed": state.processed or 0,
        "total": state.total or 0,
        "started_at": state.started_at,
        "cancel_requested": state.cancel_requested or False,
        "eta_seconds": eta_seconds,
    }


def _queue_status_payload(settings: Settings) -> dict[str, object]:
    if not settings.queue_enabled:
        return {"enabled": False, "length": None, "total": 0, "in_progress": 0, "done": 0, "paused": False}
    stats = queue_stats(settings) or {"length": 0, "total": 0, "in_progress": 0, "done": 0}
    return {"enabled": True, **stats, "paused": is_paused(settings)}


def _document_stats_payload(db: Session) -> dict[str, object]:
    total = db.query(Document).count()
    embeddings = db.query(Document.id).filter(exists().where(DocumentEmbedding.doc_id == Document.id)).count()
    vision = db.query(Document.id).filter(
        exists().where(
            (DocumentPageText.doc_id == Document.id) & (DocumentPageText.source == "vision_ocr")
        )
    ).count()
    suggestions = db.query(Document.id).filter(exists().where(DocumentSuggestion.doc_id == Document.id)).count()
    fully_processed = db.query(Document.id).filter(
        exists().where(DocumentEmbedding.doc_id == Document.id),
        exists().where(
            (DocumentPageText.doc_id == Document.id) & (DocumentPageText.source == "vision_ocr")
        ),
        exists().where(DocumentSuggestion.doc_id == Document.id),
    ).count()
    unprocessed = max(0, total - fully_processed)
    return {
        "total": total,
        "processed": embeddings,
        "unprocessed": unprocessed,
        "embeddings": embeddings,
        "vision": vision,
        "suggestions": suggestions,
        "fully_processed": fully_processed,
    }


def _embeddings_status_payload(settings: Settings, db: Session) -> dict[str, object]:
    state = db.get(SyncState, "embeddings")
    if settings.queue_enabled:
        stats = queue_stats(settings) or {"length": 0, "total": 0, "in_progress": 0, "done": 0}
        status = "running" if (stats["length"] > 0 or stats["in_progress"] > 0) else "idle"
        if status == "running" and state and not state.started_at:
            state.started_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
            state.status = "running"
            db.commit()
        started_at = state.started_at if state else None
        eta_seconds = estimate_eta_seconds(started_at, stats["done"], stats["total"])
        return {
            "status": status,
            "processed": stats["done"],
            "total": stats["total"],
            "started_at": started_at,
            "last_synced_at": state.last_synced_at if state else None,
            "cancel_requested": state.cancel_requested if state else False,
            "eta_seconds": eta_seconds,
        }
    if not state:
        return {"status": "idle", "processed": 0, "total": 0, "started_at": None}
    eta_seconds = estimate_eta_seconds(state.started_at, state.processed, state.total)
    return {
        "status": state.status or "idle",
        "processed": state.processed or 0,
        "total": state.total or 0,
        "started_at": state.started_at,
        "last_synced_at": state.last_synced_at,
        "cancel_requested": state.cancel_requested or False,
        "eta_seconds": eta_seconds,
    }


@router.get("/stream")
async def status_stream(settings: Settings = Depends(get_settings)):
    interval = max(1, settings.status_stream_interval_seconds)

    async def event_generator():
        while True:
            db = SessionLocal()
            try:
                payload = {
                    "status": _status_payload(settings),
                    "queue": _queue_status_payload(settings),
                    "sync": _sync_state_payload(db, "documents"),
                    "embeddings": _embeddings_status_payload(settings, db),
                    "stats": _document_stats_payload(db),
                    "timestamp": int(time.time()),
                }
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            finally:
                db.close()
            await asyncio.sleep(interval)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
