from __future__ import annotations

from typing import Any

from app.config import load_settings
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
    monkeypatch.setenv("WEAVIATE_HTTP_HOST", "weaviate-http")
    settings = load_settings()

    payload = _status_payload(settings)

    assert payload["vector_store_provider"] == "weaviate"
    assert payload["vector_store_url"] == "http://weaviate-http:8080"
