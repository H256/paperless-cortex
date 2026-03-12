from __future__ import annotations

from typing import Any

from app.config import load_settings
from app.services.ai import llm_client
from app.services.integrations import paperless
from app.services.search import qdrant


def test_paperless_client_pool_reuses_client(monkeypatch: Any) -> None:
    monkeypatch.setenv("PAPERLESS_BASE_URL", "http://paperless.local")
    monkeypatch.setenv("PAPERLESS_API_TOKEN", "token-123")
    monkeypatch.setenv("HTTPX_VERIFY_TLS", "0")
    settings = load_settings()
    paperless.clear_client_pool()

    with paperless.client(settings) as first, paperless.client(settings) as second:
        assert first is second

    paperless.clear_client_pool()


def test_qdrant_client_pool_keys_by_timeout(monkeypatch: Any) -> None:
    monkeypatch.setenv("QDRANT_URL", "http://qdrant.local")
    monkeypatch.setenv("HTTPX_VERIFY_TLS", "0")
    settings = load_settings()
    qdrant.clear_client_pool()

    with qdrant.client(settings, timeout=5) as first:
        with qdrant.client(settings, timeout=5) as second:
            assert first is second
        with qdrant.client(settings, timeout=10) as third:
            assert first is not third

    qdrant.clear_client_pool()


def test_llm_client_pool_reuses_client(monkeypatch: Any) -> None:
    monkeypatch.setenv("LLM_BASE_URL", "http://llm.local")
    monkeypatch.setenv("HTTPX_VERIFY_TLS", "1")
    settings = load_settings()
    llm_client.clear_client_pool()

    with llm_client.client(settings, timeout=10) as first, llm_client.client(
        settings, timeout=10
    ) as second:
        assert first is second

    llm_client.clear_client_pool()
