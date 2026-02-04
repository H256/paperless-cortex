from __future__ import annotations

from app.config import Settings
from app.services import qdrant


def ensure_ollama_ready(settings: Settings, *, require_model: bool = True) -> None:
    if not settings.ollama_base_url:
        raise RuntimeError("OLLAMA_BASE_URL not set")
    if require_model and not settings.ollama_model:
        raise RuntimeError("OLLAMA_BASE_URL/OLLAMA_MODEL not set")


def ensure_qdrant_ready(settings: Settings) -> None:
    qdrant.base_url(settings)
    qdrant.collection_name(settings)
