from __future__ import annotations

from app.config import load_settings
from app.routes.status import _status_payload

def test_status_includes_evidence_runtime_config(api_client):
    response = api_client.get("/status")
    assert response.status_code == 200
    payload = response.json()
    assert "evidence_max_pages" in payload
    assert "evidence_min_snippet_chars" in payload


def test_status_includes_effective_chat_model(monkeypatch):
    monkeypatch.setenv("TEXT_MODEL", "text-default")
    monkeypatch.setenv("CHAT_MODEL", "chat-override")
    settings = load_settings()
    payload = _status_payload(settings)
    assert payload["chat_model"] == "chat-override"


def test_status_chat_model_falls_back_to_text_model(monkeypatch):
    monkeypatch.delenv("CHAT_MODEL", raising=False)
    monkeypatch.setenv("TEXT_MODEL", "text-default")
    settings = load_settings()
    payload = _status_payload(settings)
    assert payload["chat_model"] == "text-default"
