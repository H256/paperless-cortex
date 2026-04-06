from __future__ import annotations

import os
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import load_settings
from app.models import RuntimeModelProviderOverride
from app.services.runtime.model_providers import decrypt_api_key, provider_base_url, provider_model


def test_model_provider_settings_get_returns_effective_roles(
    api_client: Any,
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("LLM_BASE_URL", "http://llm-default")
    monkeypatch.setenv("OCR_CHAT_BASE", "http://chat-default")
    monkeypatch.setenv("OCR_VISION_BASE", "http://vision-default")
    monkeypatch.setenv("TEXT_MODEL", "text-default")
    monkeypatch.setenv("CHAT_MODEL", "chat-default")
    monkeypatch.setenv("EMBEDDING_MODEL", "embed-default")
    monkeypatch.setenv("VISION_MODEL", "vision-default")

    response = api_client.get("/settings/model-providers")

    assert response.status_code == 200
    payload = response.json()
    items = {item["role"]: item for item in payload["items"]}
    assert set(items) == {"text", "chat", "embedding", "vision"}
    assert items["text"]["base_url"] == "http://chat-default"
    assert items["chat"]["base_url"] == "http://chat-default"
    assert items["embedding"]["base_url"] == "http://llm-default"
    assert items["vision"]["base_url"] == "http://vision-default"
    assert items["chat"]["model"] == "chat-default"


def test_model_provider_settings_put_persists_encrypted_override(
    api_client: Any,
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("LLM_BASE_URL", "http://llm-default")
    monkeypatch.setenv("CHAT_MODEL", "chat-default")

    response = api_client.put(
        "/settings/model-providers",
        json={
            "items": [
                {
                    "role": "chat",
                    "base_url": "https://chat.example/v1/../",
                    "model": "gpt-live",
                    "api_key": "super-secret-key",
                }
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()
    chat_item = next(item for item in payload["items"] if item["role"] == "chat")
    assert chat_item["base_url"] == "https://chat.example/v1/.."
    assert chat_item["model"] == "gpt-live"
    assert chat_item["api_key_configured"] is True
    assert chat_item["api_key_hint"] == "...-key"
    assert "api_key" not in chat_item

    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        row = db.get(RuntimeModelProviderOverride, "chat")
        assert row is not None
        assert row.api_key_encrypted
        assert row.api_key_encrypted != "super-secret-key"
        settings = load_settings(apply_runtime_overrides=False)
        assert decrypt_api_key(settings, row.api_key_encrypted) == "super-secret-key"

    refreshed = load_settings()
    assert provider_base_url(refreshed, "chat") == "https://chat.example/v1/.."
    assert provider_model(refreshed, "chat") == "gpt-live"


def test_model_provider_settings_put_can_clear_stored_key(
    api_client: Any,
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("LLM_BASE_URL", "http://llm-default")

    first_response = api_client.put(
        "/settings/model-providers",
        json={
            "items": [
                {
                    "role": "embedding",
                    "base_url": "http://embed-live",
                    "model": "embed-live",
                    "api_key": "embed-secret",
                }
            ]
        },
    )
    assert first_response.status_code == 200

    clear_response = api_client.put(
        "/settings/model-providers",
        json={"items": [{"role": "embedding", "base_url": None, "model": None, "clear_api_key": True}]},
    )

    assert clear_response.status_code == 200
    payload = clear_response.json()
    embedding_item = next(item for item in payload["items"] if item["role"] == "embedding")
    assert embedding_item["api_key_configured"] is False

    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        row = db.get(RuntimeModelProviderOverride, "embedding")
        assert row is not None
        assert row.api_key_encrypted is None


def test_model_provider_discovery_route_returns_models(
    api_client: Any,
    monkeypatch: Any,
) -> None:
    from app.routes import settings as settings_routes

    monkeypatch.setattr(
        settings_routes,
        "discover_models",
        lambda **_kwargs: (True, "ok", ["gpt-4.1-mini", "text-embedding-3-small"]),
    )

    response = api_client.post(
        "/settings/model-providers/discover",
        json={"base_url": "http://llm.local", "api_key": "secret"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "detail": "ok",
        "models": ["gpt-4.1-mini", "text-embedding-3-small"],
    }
