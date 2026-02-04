from __future__ import annotations

import time

from fastapi import APIRouter, Depends

from app.config import Settings
from app.deps import get_settings
from app.services.queue import worker_status
from app.services import paperless
from app.services import llm_client
from app.api_models import StatusResponse

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


@router.get("", response_model=StatusResponse)
def status(settings: Settings = Depends(get_settings)):
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
