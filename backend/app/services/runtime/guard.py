from __future__ import annotations

from typing import TYPE_CHECKING

from app.services.search import vector_store

if TYPE_CHECKING:
    from app.config import Settings


def ensure_llm_base_ready(settings: Settings) -> None:
    if not settings.llm_base_url:
        raise RuntimeError("LLM_BASE_URL not set")


def ensure_text_llm_ready(settings: Settings) -> None:
    ensure_llm_base_ready(settings)
    if not settings.text_model:
        raise RuntimeError("TEXT_MODEL not set")


def resolve_chat_model(settings: Settings) -> str | None:
    return settings.chat_model or settings.text_model


def ensure_chat_llm_ready(settings: Settings) -> None:
    ensure_llm_base_ready(settings)
    if not resolve_chat_model(settings):
        raise RuntimeError("CHAT_MODEL or TEXT_MODEL not set")


def ensure_embedding_llm_ready(settings: Settings) -> None:
    ensure_llm_base_ready(settings)
    if not settings.embedding_model:
        raise RuntimeError("EMBEDDING_MODEL not set")


def ensure_vision_llm_ready(settings: Settings, *, require_model: bool = True) -> None:
    ensure_llm_base_ready(settings)
    if require_model and not settings.vision_model:
        raise RuntimeError("VISION_MODEL not set")


def ensure_vector_store_ready(settings: Settings) -> None:
    vector_store.ensure_ready(settings)


def ensure_qdrant_ready(settings: Settings) -> None:
    ensure_vector_store_ready(settings)
