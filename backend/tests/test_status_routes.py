from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from app.config import load_settings
from app.routes import status as status_routes
from app.routes.status import _status_payload


def test_status_includes_evidence_runtime_config(api_client: Any) -> None:
    response = api_client.get("/status")
    assert response.status_code == 200
    payload = response.json()
    assert "evidence_max_pages" in payload
    assert "evidence_min_snippet_chars" in payload


def test_status_includes_effective_chat_model(monkeypatch: Any) -> None:
    monkeypatch.setenv("TEXT_MODEL", "text-default")
    monkeypatch.setenv("CHAT_MODEL", "chat-override")
    settings = load_settings()
    payload = _status_payload(settings)
    assert payload["chat_model"] == "chat-override"


def test_status_chat_model_falls_back_to_text_model(monkeypatch: Any) -> None:
    monkeypatch.delenv("CHAT_MODEL", raising=False)
    monkeypatch.setenv("TEXT_MODEL", "text-default")
    settings = load_settings()
    payload = _status_payload(settings)
    assert payload["chat_model"] == "text-default"


def test_status_includes_vector_store_runtime_config(monkeypatch: Any) -> None:
    monkeypatch.setenv("VECTOR_STORE_PROVIDER", "weaviate")
    monkeypatch.delenv("VECTOR_STORE_URL", raising=False)
    monkeypatch.setenv("WEAVIATE_HTTP_HOST", "weaviate-http")
    monkeypatch.setenv("WEAVIATE_HTTP_PORT", "8080")
    settings = load_settings()

    payload = _status_payload(settings)

    assert payload["vector_store_provider"] == "weaviate"
    assert payload["vector_store_url"] == "http://weaviate-http:8080"


@pytest.mark.anyio
async def test_status_stream_offloads_blocking_payload_build(monkeypatch: Any) -> None:
    monkeypatch.setenv("STATUS_STREAM_INTERVAL_SECONDS", "1")
    settings = load_settings()

    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    async def fake_to_thread(func: Any, *args: Any, **kwargs: Any) -> dict[str, Any]:
        calls.append((args, kwargs))
        return {"status": "ok", "timestamp": 1}

    monkeypatch.setattr(status_routes.asyncio, "to_thread", fake_to_thread)

    response = await status_routes.status_stream(settings)
    iterator = response.body_iterator
    assert isinstance(iterator, AsyncIterator)
    payload = await anext(iterator)

    assert payload == 'data: {"status": "ok", "timestamp": 1}\n\n'
    assert calls == [((settings,), {"interval_seconds": 1})]
