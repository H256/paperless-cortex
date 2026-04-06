from __future__ import annotations

from typing import TYPE_CHECKING

from app.services.runtime.model_providers import provider_base_url, provider_model
from app.services.search import vector_store

if TYPE_CHECKING:
    from app.config import Settings


def ensure_llm_base_ready(settings: Settings) -> None:
    if not provider_base_url(settings, "text"):
        raise RuntimeError("LLM_BASE_URL not set")


def ensure_text_llm_ready(settings: Settings) -> None:
    if not provider_base_url(settings, "text"):
        raise RuntimeError("TEXT LLM base URL not set")
    if not provider_model(settings, "text"):
        raise RuntimeError("TEXT_MODEL not set")


def resolve_chat_model(settings: Settings) -> str | None:
    return provider_model(settings, "chat") or provider_model(settings, "text")


def ensure_chat_llm_ready(settings: Settings) -> None:
    if not provider_base_url(settings, "chat"):
        raise RuntimeError("CHAT LLM base URL not set")
    if not resolve_chat_model(settings):
        raise RuntimeError("CHAT_MODEL or TEXT_MODEL not set")


def ensure_embedding_llm_ready(settings: Settings) -> None:
    if not provider_base_url(settings, "embedding"):
        raise RuntimeError("EMBEDDING LLM base URL not set")
    if not provider_model(settings, "embedding"):
        raise RuntimeError("EMBEDDING_MODEL not set")


def ensure_vision_llm_ready(settings: Settings, *, require_model: bool = True) -> None:
    if not provider_base_url(settings, "vision"):
        raise RuntimeError("VISION LLM base URL not set")
    if require_model and not provider_model(settings, "vision"):
        raise RuntimeError("VISION_MODEL not set")


def ensure_vector_store_ready(settings: Settings) -> None:
    vector_store.ensure_ready(settings)


def ensure_qdrant_ready(settings: Settings) -> None:
    ensure_vector_store_ready(settings)
