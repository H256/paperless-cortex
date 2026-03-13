from __future__ import annotations

from contextlib import contextmanager
from typing import Any

import pytest

from app.config import load_settings
from app.services.search import vector_store


def test_vector_store_defaults_to_qdrant_provider(monkeypatch: Any) -> None:
    monkeypatch.setenv("VECTOR_STORE_PROVIDER", "qdrant")
    monkeypatch.delenv("VECTOR_STORE_URL", raising=False)
    monkeypatch.delenv("VECTOR_STORE_COLLECTION", raising=False)
    monkeypatch.delenv("VECTOR_STORE_CENTROID_COLLECTION", raising=False)
    monkeypatch.delenv("WEAVIATE_HTTP_HOST", raising=False)
    monkeypatch.delenv("WEAVIATE_HTTP_PORT", raising=False)
    monkeypatch.delenv("WEAVIATE_GRPC_HOST", raising=False)
    monkeypatch.delenv("WEAVIATE_GRPC_PORT", raising=False)
    monkeypatch.delenv("WEAVIATE_COLLECTION", raising=False)
    monkeypatch.delenv("WEAVIATE_CENTROID_COLLECTION", raising=False)
    monkeypatch.setenv("QDRANT_COLLECTION", "paperless_chunks")
    settings = load_settings()

    assert vector_store.provider_name(settings) == "qdrant"
    assert vector_store.display_name(settings) == "Qdrant"


def test_vector_store_selects_weaviate_provider(monkeypatch: Any) -> None:
    monkeypatch.setenv("VECTOR_STORE_PROVIDER", "weaviate")
    monkeypatch.setenv("WEAVIATE_HTTP_HOST", "weaviate")
    settings = load_settings()

    assert vector_store.provider_name(settings) == "weaviate"
    assert vector_store.display_name(settings) == "Weaviate"


def test_vector_store_rejects_unknown_provider(monkeypatch: Any) -> None:
    monkeypatch.setenv("VECTOR_STORE_PROVIDER", "unknown-store")
    settings = load_settings()

    with pytest.raises(RuntimeError, match="Unsupported vector store provider: unknown-store"):
        vector_store.get_vector_store_adapter(settings)


@contextmanager
def _noop_context() -> Any:
    yield None


def test_vector_store_delegates_chunk_delete_to_weaviate(monkeypatch: Any) -> None:
    monkeypatch.setenv("VECTOR_STORE_PROVIDER", "weaviate")
    monkeypatch.setenv("WEAVIATE_HTTP_HOST", "weaviate")
    settings = load_settings()
    calls: list[str] = []

    monkeypatch.setattr(
        vector_store.weaviate_adapter,
        "delete_all_chunk_points",
        lambda _settings: calls.append("weaviate"),
    )

    vector_store.delete_all_chunk_points(settings)

    assert calls == ["weaviate"]


def test_vector_store_delegates_similarity_delete_to_qdrant(monkeypatch: Any) -> None:
    monkeypatch.setenv("VECTOR_STORE_PROVIDER", "qdrant")
    monkeypatch.setenv("QDRANT_COLLECTION", "paperless_chunks")
    settings = load_settings()
    calls: list[tuple[int | None, str]] = []

    monkeypatch.setattr(
        vector_store.qdrant_adapter,
        "delete_similarity_points",
        lambda _settings, *, doc_id=None: calls.append((doc_id, "qdrant")),
    )

    vector_store.delete_similarity_points(settings, doc_id=7)

    assert calls == [(7, "qdrant")]
