from __future__ import annotations

import time

import httpx
from fastapi import APIRouter, Depends

from app.config import Settings, load_settings
from app.services.queue import worker_status

router = APIRouter(prefix="/status", tags=["status"])


def settings_dep() -> Settings:
    return load_settings()


def check_ollama(settings: Settings) -> tuple[bool, str]:
    if not settings.ollama_base_url:
        return False, "OLLAMA_BASE_URL not set"
    try:
        with httpx.Client(timeout=5, verify=settings.httpx_verify_tls) as client:
            response = client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
            response.raise_for_status()
        return True, "ok"
    except Exception as exc:
        return False, exc.__class__.__name__


@router.get("")
def status(settings: Settings = Depends(settings_dep)):
    started = time.perf_counter()
    ollama_ok, ollama_detail = check_ollama(settings)
    worker_ok, worker_detail = worker_status(settings) if settings.queue_enabled else (False, "Queue disabled")
    return {
        "web": {"status": "UP"},
        "worker": {"status": "UP" if worker_ok else "DOWN", "detail": worker_detail},
        "ollama": {"status": "UP" if ollama_ok else "DOWN", "detail": ollama_detail},
        "paperless_base_url": settings.paperless_base_url or "",
        "latency_ms": int((time.perf_counter() - started) * 1000),
    }
