from __future__ import annotations

from typing import Any

import pytest

from app.config import load_settings


def test_settings_exposes_domain_config_views(monkeypatch: Any) -> None:
    monkeypatch.setenv("LOG_LEVEL", "debug")
    monkeypatch.setenv("LOG_JSON", "1")
    monkeypatch.setenv("PAPERLESS_BASE_URL", "http://paperless.local/")
    monkeypatch.setenv("PAPERLESS_API_TOKEN", "token-123")
    monkeypatch.setenv("QUEUE_ENABLED", "1")
    monkeypatch.setenv("REDIS_HOST", "redis")
    monkeypatch.setenv("QDRANT_URL", "http://qdrant")
    monkeypatch.setenv("QDRANT_COLLECTION", "docs")
    monkeypatch.setenv("EMBEDDING_BATCH_SIZE", "32")
    monkeypatch.setenv("EMBED_ON_SYNC", "1")
    monkeypatch.setenv("CHUNK_MODE", "semantic")
    monkeypatch.setenv("HTTPX_VERIFY_TLS", "0")
    monkeypatch.setenv("WRITEBACK_EXECUTE_ENABLED", "1")

    settings = load_settings()

    assert settings.logging.level == "DEBUG"
    assert settings.logging.json is True
    assert settings.paperless.base_url == "http://paperless.local"
    assert settings.paperless.api_token == "token-123"
    assert settings.queue.enabled is True
    assert settings.queue.redis_host == "redis"
    assert settings.qdrant.url == "http://qdrant"
    assert settings.qdrant.collection == "docs"
    assert settings.embeddings.batch_size == 32
    assert settings.embeddings.embed_on_sync is True
    assert settings.chunking.mode == "semantic"
    assert settings.http.verify_tls is False
    assert settings.writeback.execute_enabled is True

    # Flat compatibility remains for the rest of the codebase.
    assert settings.paperless_base_url == settings.paperless.base_url
    assert settings.queue_enabled == settings.queue.enabled
    assert settings.embedding_batch_size == settings.embeddings.batch_size


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("LOG_JSON", "maybe", "Invalid boolean for LOG_JSON"),
        ("CHUNK_MODE", "weird", "Invalid CHUNK_MODE"),
        ("EMBEDDING_BATCH_SIZE", "abc", "invalid literal"),
    ],
)
def test_load_settings_validates_invalid_values(
    monkeypatch: Any,
    name: str,
    value: str,
    message: str,
) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ValueError, match=message):
        load_settings()
