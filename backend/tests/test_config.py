from __future__ import annotations

from typing import Any

import pytest

from app.config import load_settings


def test_settings_exposes_domain_config_views(monkeypatch: Any) -> None:
    monkeypatch.setenv("VECTOR_STORE_PROVIDER", "qdrant")
    monkeypatch.setenv("VECTOR_STORE_URL", "")
    monkeypatch.setenv("VECTOR_STORE_COLLECTION", "")
    monkeypatch.setenv("VECTOR_STORE_CENTROID_COLLECTION", "")
    monkeypatch.setenv("WEAVIATE_HTTP_HOST", "")
    monkeypatch.setenv("WEAVIATE_HTTP_PORT", "")
    monkeypatch.setenv("WEAVIATE_COLLECTION", "")
    monkeypatch.setenv("WEAVIATE_CENTROID_COLLECTION", "")
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
    assert settings.vector_store.provider == "qdrant"
    assert settings.vector_store.url == "http://qdrant"
    assert settings.vector_store.collection == "docs"
    assert settings.embeddings.batch_size == 32
    assert settings.embeddings.embed_on_sync is True
    assert settings.chunking.mode == "semantic"
    assert settings.http.verify_tls is False
    assert settings.writeback.execute_enabled is True

    # Flat compatibility remains for the rest of the codebase.
    assert settings.paperless_base_url == settings.paperless.base_url
    assert settings.queue_enabled == settings.queue.enabled
    assert settings.embedding_batch_size == settings.embeddings.batch_size


def test_vector_store_config_prefers_generic_over_legacy_env(monkeypatch: Any) -> None:
    monkeypatch.setenv("VECTOR_STORE_PROVIDER", "qdrant")
    monkeypatch.setenv("VECTOR_STORE_URL", "http://vector")
    monkeypatch.setenv("VECTOR_STORE_COLLECTION", "vector_docs")
    monkeypatch.setenv("VECTOR_STORE_API_KEY", "vector-key")
    monkeypatch.setenv("QDRANT_URL", "http://legacy-qdrant")
    monkeypatch.setenv("QDRANT_COLLECTION", "legacy_docs")

    settings = load_settings()

    assert settings.vector_store.provider == "qdrant"
    assert settings.vector_store.url == "http://vector"
    assert settings.vector_store.collection == "vector_docs"
    assert settings.vector_store.api_key == "vector-key"
    assert settings.qdrant.url == "http://legacy-qdrant"
    assert settings.qdrant.collection == "legacy_docs"


def test_weaviate_vector_store_settings_build_http_grpc_split(monkeypatch: Any) -> None:
    monkeypatch.setenv("VECTOR_STORE_PROVIDER", "weaviate")
    monkeypatch.setenv("VECTOR_STORE_URL", "")
    monkeypatch.setenv("VECTOR_STORE_COLLECTION", "")
    monkeypatch.setenv("VECTOR_STORE_CENTROID_COLLECTION", "")
    monkeypatch.setenv("WEAVIATE_HTTP_HOST", "weaviate-http")
    monkeypatch.setenv("WEAVIATE_HTTP_PORT", "8081")
    monkeypatch.setenv("WEAVIATE_GRPC_HOST", "weaviate-grpc")
    monkeypatch.setenv("WEAVIATE_GRPC_PORT", "50052")
    monkeypatch.setenv("WEAVIATE_COLLECTION", "paperless_chunks_v2")
    monkeypatch.setenv("WEAVIATE_CENTROID_COLLECTION", "")

    settings = load_settings()

    assert settings.vector_store.provider == "weaviate"
    assert settings.vector_store.url == "http://weaviate-http:8081"
    assert settings.vector_store.collection == "paperless_chunks_v2"
    assert settings.vector_store.centroid_collection == "paperless_chunks_v2_centroids"
    assert settings.weaviate_http_host == "weaviate-http"
    assert settings.weaviate_http_port == 8081
    assert settings.weaviate_grpc_host == "weaviate-grpc"
    assert settings.weaviate_grpc_port == 50052


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
