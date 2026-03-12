from __future__ import annotations

from typing import Any

import pytest

from app.config import load_settings
from app.services.search import vector_store


def test_vector_store_defaults_to_qdrant_provider(monkeypatch: Any) -> None:
    monkeypatch.delenv("VECTOR_STORE_PROVIDER", raising=False)
    settings = load_settings()

    assert vector_store.provider_name(settings) == "qdrant"
    assert vector_store.display_name(settings) == "Qdrant"


def test_vector_store_rejects_unsupported_provider(monkeypatch: Any) -> None:
    monkeypatch.setenv("VECTOR_STORE_PROVIDER", "weaviate")
    settings = load_settings()

    with pytest.raises(RuntimeError, match="Unsupported vector store provider: weaviate"):
        vector_store.get_vector_store_adapter(settings)
