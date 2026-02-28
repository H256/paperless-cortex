from __future__ import annotations

from app.config import Settings
from app.services.search import qdrant


def ensure_llm_base_ready(settings: Settings) -> None:
    if not settings.llm_base_url:
        raise RuntimeError("LLM_BASE_URL not set")


def ensure_text_llm_ready(settings: Settings) -> None:
    ensure_llm_base_ready(settings)
    if not settings.text_model:
        raise RuntimeError("TEXT_MODEL not set")


def ensure_embedding_llm_ready(settings: Settings) -> None:
    ensure_llm_base_ready(settings)
    if not settings.embedding_model:
        raise RuntimeError("EMBEDDING_MODEL not set")


def ensure_vision_llm_ready(settings: Settings, *, require_model: bool = True) -> None:
    ensure_llm_base_ready(settings)
    if require_model and not settings.vision_model:
        raise RuntimeError("VISION_MODEL not set")


def ensure_qdrant_ready(settings: Settings) -> None:
    qdrant.base_url(settings)
    qdrant.collection_name(settings)
