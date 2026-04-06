from __future__ import annotations

import asyncio
import json
import threading
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api_models import StatusResponse
from app.db import SessionLocal
from app.deps import get_settings
from app.models import SyncState
from app.services.ai import llm_client
from app.services.documents.document_stats import compute_document_stats
from app.services.documents.document_stats_cache import get_cached_document_stats
from app.services.integrations import paperless
from app.services.pipeline.queue import is_paused, queue_stats, worker_status
from app.services.runtime.guard import resolve_chat_model
from app.services.runtime.metrics import snapshot_metrics
from app.services.runtime.model_providers import provider_api_key, provider_base_url, provider_model
from app.services.runtime.time_utils import estimate_eta_seconds
from app.version import API_VERSION, APP_VERSION

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.orm import Session

    from app.config import Settings

router = APIRouter(prefix="/status", tags=["status"])
_model_cache: dict[tuple[str, str], dict[str, Any]] = {}
_stream_cache_lock = threading.Lock()
_stream_cache: dict[str, Any] = {"ts": 0.0, "payload": None}


def _fetch_models(
    settings: Settings,
    *,
    base_url: str | None,
    api_key: str | None,
) -> tuple[bool, str, list[dict[str, Any]]]:
    ttl = max(0, settings.status_llm_models_ttl_seconds)
    now = time.time()
    normalized_base = str(base_url or "").rstrip("/")
    normalized_api_key = str(api_key or "").strip()
    cache_key = (normalized_base, normalized_api_key[-8:])
    cached = _model_cache.get(cache_key)
    if cached and ttl and (now - float(cached.get("ts") or 0.0)) < ttl:
        cached_models = cached.get("models")
        models = cached_models if isinstance(cached_models, list) else []
        return bool(cached.get("ok")), str(cached.get("detail")), list(models)
    if not normalized_base:
        return False, "LLM_BASE_URL not set", []
    try:
        with llm_client.client(settings, timeout=5) as client:
            response = client.get(
                f"{normalized_base}/v1/models",
                headers={"Authorization": f"Bearer {normalized_api_key}"} if normalized_api_key else {},
            )
            response.raise_for_status()
            payload = response.json()
        models = payload.get("data") or []
        if not isinstance(models, list):
            return False, "Invalid models payload", []
        data = [m for m in models if isinstance(m, dict)]
        _model_cache[cache_key] = {"ts": now, "ok": True, "detail": "ok", "models": data}
        return True, "ok", data
    except (httpx.HTTPError, RuntimeError, ValueError) as exc:
        _model_cache[cache_key] = {
            "ts": now,
            "ok": False,
            "detail": exc.__class__.__name__,
            "models": [],
        }
        return False, exc.__class__.__name__, []


def _model_status(models: list[dict[str, object]], model_name: str | None) -> tuple[bool, str]:
    if not model_name:
        return False, "model not set"
    for model in models:
        if model.get("id") == model_name:
            status = model.get("status") or {}
            value = status.get("value") if isinstance(status, dict) else None
            if isinstance(value, str) and value:
                return value == "loaded", value
            return True, "unknown"
    return False, "not found"


def _status_payload(settings: Settings) -> dict[str, Any]:
    started = time.perf_counter()
    text_url = provider_base_url(settings, "text")
    chat_url = provider_base_url(settings, "chat")
    embedding_url = provider_base_url(settings, "embedding")
    vision_url = provider_base_url(settings, "vision")
    text_api_key = provider_api_key(settings, "text")
    chat_api_key = provider_api_key(settings, "chat")
    embedding_api_key = provider_api_key(settings, "embedding")
    vision_api_key = provider_api_key(settings, "vision")
    text_llm_ok, text_llm_detail, text_models = _fetch_models(
        settings, base_url=text_url, api_key=text_api_key
    )
    chat_llm_ok, chat_llm_detail, chat_models = _fetch_models(
        settings, base_url=chat_url, api_key=chat_api_key
    )
    embedding_llm_ok, embedding_llm_detail, embedding_models = _fetch_models(
        settings, base_url=embedding_url, api_key=embedding_api_key
    )
    vision_llm_ok, vision_llm_detail, vision_models = _fetch_models(
        settings, base_url=vision_url, api_key=vision_api_key
    )
    text_ok, text_detail = _model_status(text_models, provider_model(settings, "text"))
    _chat_ok, _chat_detail = _model_status(chat_models, resolve_chat_model(settings))
    embed_ok, embed_detail = _model_status(
        embedding_models, provider_model(settings, "embedding")
    )
    vision_ok, vision_detail = _model_status(vision_models, provider_model(settings, "vision"))
    llm_ok = text_llm_ok and chat_llm_ok and embedding_llm_ok and vision_llm_ok
    llm_detail = (
        "ok"
        if llm_ok
        else next(
            (
                detail
                for detail, ok in (
                    (text_llm_detail, text_llm_ok),
                    (chat_llm_detail, chat_llm_ok),
                    (embedding_llm_detail, embedding_llm_ok),
                    (vision_llm_detail, vision_llm_ok),
                )
                if not ok
            ),
            "unknown",
        )
    )
    worker_ok, worker_detail = (
        worker_status(settings) if settings.queue_enabled else (False, "Queue disabled")
    )
    paperless_base = paperless.base_url(settings) or ""
    return {
        "web": {"status": "UP"},
        "worker": {"status": "UP" if worker_ok else "DOWN", "detail": worker_detail},
        "llm": {"status": "UP" if llm_ok else "DOWN", "detail": llm_detail},
        "llm_text": {"status": "UP" if text_ok else "DOWN", "detail": text_detail},
        "llm_embedding": {"status": "UP" if embed_ok else "DOWN", "detail": embed_detail},
        "llm_vision": {"status": "UP" if vision_ok else "DOWN", "detail": vision_detail},
        "paperless_base_url": paperless_base,
        "llm_base_url": text_url,
        "text_base_url": text_url,
        "chat_base_url": chat_url,
        "embedding_base_url": embedding_url,
        "vision_base_url": vision_url,
        "qdrant_url": settings.qdrant_url,
        "vector_store_provider": settings.vector_store.provider,
        "vector_store_url": settings.vector_store.url,
        "redis_host": settings.redis_host,
        "text_model": provider_model(settings, "text"),
        "chat_model": resolve_chat_model(settings),
        "embedding_model": provider_model(settings, "embedding"),
        "vision_model": provider_model(settings, "vision"),
        "evidence_max_pages": settings.evidence_max_pages,
        "evidence_min_snippet_chars": settings.evidence_min_snippet_chars,
        "app_version": APP_VERSION,
        "api_version": API_VERSION,
        "frontend_version": APP_VERSION,
        "latency_ms": int((time.perf_counter() - started) * 1000),
    }


@router.get("", response_model=StatusResponse)
def status(settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    """Return the consolidated application health/config snapshot."""
    return _status_payload(settings)


@router.get("/metrics")
def metrics() -> dict[str, list[dict[str, Any]]]:
    """Return in-memory backend counters and timing aggregates for observability."""
    return snapshot_metrics()


def _sync_state_payload(db: Session, key: str) -> dict[str, Any]:
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


def _queue_status_payload(settings: Settings) -> dict[str, Any]:
    if not settings.queue_enabled:
        return {
            "enabled": False,
            "length": None,
            "total": 0,
            "in_progress": 0,
            "done": 0,
            "paused": False,
        }
    stats = queue_stats(settings) or {"length": 0, "total": 0, "in_progress": 0, "done": 0}
    return {"enabled": True, **stats, "paused": is_paused(settings)}


def _document_stats_payload(db: Session) -> dict[str, Any]:
    return get_cached_document_stats(db, build_payload=compute_document_stats)


def _embeddings_status_payload(settings: Settings, db: Session) -> dict[str, Any]:
    state = db.get(SyncState, "embeddings")
    if settings.queue_enabled:
        stats = queue_stats(settings) or {"length": 0, "total": 0, "in_progress": 0, "done": 0}
        status = "running" if (stats["length"] > 0 or stats["in_progress"] > 0) else "idle"
        started_at = state.started_at if state else None
        if status == "running" and not started_at:
            started_at = datetime.now(UTC).isoformat()
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


def _build_stream_payload(settings: Settings) -> dict[str, Any]:
    db = SessionLocal()
    try:
        return {
            "status": _status_payload(settings),
            "queue": _queue_status_payload(settings),
            "sync": _sync_state_payload(db, "documents"),
            "embeddings": _embeddings_status_payload(settings, db),
            "stats": _document_stats_payload(db),
            "timestamp": int(time.time()),
        }
    finally:
        db.close()


def _get_cached_stream_payload(settings: Settings, *, interval_seconds: int) -> dict[str, Any]:
    ttl = max(1, int(interval_seconds)) / 2.0
    now = time.time()
    with _stream_cache_lock:
        cached_ts = float(_stream_cache.get("ts") or 0.0)
        cached_payload = _stream_cache.get("payload")
        if isinstance(cached_payload, dict) and (now - cached_ts) < ttl:
            return cached_payload
    payload = _build_stream_payload(settings)
    with _stream_cache_lock:
        _stream_cache["ts"] = now
        _stream_cache["payload"] = payload
    return payload


@router.get("/stream")
async def status_stream(settings: Settings = Depends(get_settings)) -> StreamingResponse:
    """Stream the consolidated app, queue, sync, and stats payload as server-sent events."""
    interval = max(1, settings.status_stream_interval_seconds)

    async def event_generator() -> AsyncIterator[str]:
        while True:
            payload = await asyncio.to_thread(
                _get_cached_stream_payload,
                settings,
                interval_seconds=interval,
            )
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            await asyncio.sleep(interval)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
