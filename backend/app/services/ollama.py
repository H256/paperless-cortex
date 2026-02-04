from __future__ import annotations

import logging

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)
_model_ready: set[str] = set()


def base_url(settings: Settings) -> str:
    if not settings.ollama_base_url:
        raise RuntimeError("OLLAMA_BASE_URL not set")
    return settings.ollama_base_url.rstrip("/")


def client(settings: Settings, timeout: float | None) -> httpx.Client:
    return httpx.Client(timeout=timeout, verify=settings.httpx_verify_tls)


def ensure_model(settings: Settings, model: str) -> None:
    if model in _model_ready:
        return
    base = base_url(settings)
    with client(settings, timeout=30) as http:
        response = http.get(f"{base}/api/tags")
        response.raise_for_status()
        data = response.json()
        models = {m.get("name") for m in data.get("models", []) if isinstance(m, dict)}
        if model in models:
            _model_ready.add(model)
            return
        logger.info("Ollama pull model=%s", model)
        pull = http.post(f"{base}/api/pull", json={"name": model, "stream": False}, timeout=300)
        pull.raise_for_status()
        _model_ready.add(model)
