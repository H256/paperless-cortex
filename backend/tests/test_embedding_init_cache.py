from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from app.config import load_settings
from app.services.search import embedding_init

if TYPE_CHECKING:
    from collections.abc import Iterator

    from pytest import MonkeyPatch


@pytest.fixture(autouse=True)
def _clear_probe_cache() -> Iterator[None]:
    embedding_init._PROBED_DIMENSIONS.clear()
    yield
    embedding_init._PROBED_DIMENSIONS.clear()


def _patch_settings(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("VECTOR_STORE_PROVIDER", "qdrant")
    monkeypatch.setenv("VECTOR_STORE_COLLECTION", "test_collection")
    monkeypatch.setenv("EMBEDDING_MODEL", "test-embed")


def test_ensure_uses_stored_dimension_without_llm_probe(
    monkeypatch: MonkeyPatch,
) -> None:
    """When the collection already exists with a stored dimension, no LLM call is made."""
    _patch_settings(monkeypatch)
    settings = load_settings()

    probe_calls: list[str] = []
    monkeypatch.setattr(
        embedding_init, "embed_text", lambda _s, text: probe_calls.append(text) or [0.1, 0.2, 0.3]
    )
    monkeypatch.setattr(
        embedding_init.vector_store, "collection_vector_size", lambda _s: 512
    )
    ensured: list[int] = []
    monkeypatch.setattr(
        embedding_init.vector_store,
        "ensure_collection",
        lambda _s, *, vector_size, distance="Cosine": ensured.append(vector_size),
    )

    embedding_init.ensure_embedding_collection(settings)
    embedding_init.ensure_embedding_collection(settings)

    assert probe_calls == []
    assert ensured == [512, 512]


def test_ensure_probes_at_most_once_when_collection_missing(
    monkeypatch: MonkeyPatch,
) -> None:
    """Two consecutive calls with no stored dimension probe the LLM at most once (cached)."""
    _patch_settings(monkeypatch)
    settings = load_settings()

    probe_calls: list[str] = []
    monkeypatch.setattr(
        embedding_init,
        "embed_text",
        lambda _s, text: (probe_calls.append(text), [0.1, 0.2, 0.3, 0.4])[1],
    )
    monkeypatch.setattr(embedding_init.vector_store, "collection_vector_size", lambda _s: None)
    ensured: list[int] = []
    monkeypatch.setattr(
        embedding_init.vector_store,
        "ensure_collection",
        lambda _s, *, vector_size, distance="Cosine": ensured.append(vector_size),
    )

    embedding_init.ensure_embedding_collection(settings)
    embedding_init.ensure_embedding_collection(settings)

    assert len(probe_calls) == 1
    assert ensured == [4, 4]


def test_ensure_probes_again_for_different_model(
    monkeypatch: MonkeyPatch,
) -> None:
    """A different embedding model (different key) is not served from the prior cache."""
    _patch_settings(monkeypatch)
    settings = load_settings()

    probe_calls: list[str] = []
    monkeypatch.setattr(
        embedding_init,
        "embed_text",
        lambda _s, text: (probe_calls.append(text), [0.1, 0.2, 0.3, 0.4, 0.5])[1],
    )
    monkeypatch.setattr(embedding_init.vector_store, "collection_vector_size", lambda _s: None)
    monkeypatch.setattr(
        embedding_init.vector_store,
        "ensure_collection",
        lambda _s, *, vector_size, distance="Cosine": None,
    )

    embedding_init.ensure_embedding_collection(settings)

    # Simulate a model switch: new settings, same provider/collection, different model.
    monkeypatch.setenv("EMBEDDING_MODEL", "other-embed")
    other = load_settings()
    embedding_init.ensure_embedding_collection(other)

    assert len(probe_calls) == 2


def test_ensure_proceeds_when_llm_down_but_collection_exists(
    monkeypatch: MonkeyPatch,
) -> None:
    """Embedding work proceeds when the LLM is down but the collection exists."""
    _patch_settings(monkeypatch)
    settings = load_settings()

    def _down(_s: Any, _text: str) -> list[float]:
        raise RuntimeError("LLM endpoint down")

    monkeypatch.setattr(embedding_init, "embed_text", _down)
    monkeypatch.setattr(
        embedding_init.vector_store, "collection_vector_size", lambda _s: 256
    )
    ensured: list[int] = []
    monkeypatch.setattr(
        embedding_init.vector_store,
        "ensure_collection",
        lambda _s, *, vector_size, distance="Cosine": ensured.append(vector_size),
    )

    embedding_init.ensure_embedding_collection(settings)

    assert ensured == [256]
