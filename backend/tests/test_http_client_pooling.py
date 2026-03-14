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


def test_llm_sdk_client_pool_reuses_sdk_client(monkeypatch: Any) -> None:
    monkeypatch.setenv("LLM_BASE_URL", "http://llm.local")
    monkeypatch.setenv("HTTPX_VERIFY_TLS", "1")
    settings = load_settings()
    created: list[object] = []

    class FakeOpenAI:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs
            self.closed = False
            created.append(self)

        def close(self) -> None:
            self.closed = True

    monkeypatch.setattr(llm_client, "OpenAI", FakeOpenAI)
    llm_client.clear_client_pool()

    first = llm_client._sdk_client(settings, timeout=10, purpose="text")
    second = llm_client._sdk_client(settings, timeout=10, purpose="text")

    assert first is second
    assert len(created) == 1

    llm_client.clear_client_pool()
    assert first.closed is True
