from __future__ import annotations

import os
from typing import Any

import pytest

from app.config import load_settings, reset_settings_cache
from app.models import RuntimeModelProviderOverride
from app.services.runtime import model_providers


@pytest.fixture()
def clean_settings_cache() -> Any:
    reset_settings_cache()
    yield
    reset_settings_cache()


def test_load_settings_caches_unchanged_env_and_rereads_on_change(
    session_factory: Any,
    monkeypatch: Any,
    clean_settings_cache: Any,
) -> None:
    # Seed one override row so _load_override_rows performs a real DB read.
    with session_factory() as db:
        db.add(RuntimeModelProviderOverride(role="chat"))
        db.commit()

    calls: list[int] = []
    real = model_providers._load_override_rows

    def counting_load(settings: Any) -> dict[str, Any]:
        calls.append(1)
        return real(settings)

    monkeypatch.setattr(model_providers, "_load_override_rows", counting_load)

    # First call: cache miss -> one DB read.
    first = load_settings()
    assert calls == [1]

    # Second call with unchanged env: cache hit -> no DB read (the issue's fix).
    second = load_settings()
    assert calls == [1]
    assert second is first

    # Changed env: new fingerprint -> cache miss -> re-reads from the DB.
    monkeypatch.setenv("LLM_BASE_URL", "http://llm-changed")
    third = load_settings()
    assert calls == [1, 1]
    assert third is not first
    assert third.llm.base_url == "http://llm-changed"


def test_upsert_provider_override_invalidates_settings_cache(
    session_factory: Any,
    monkeypatch: Any,
    clean_settings_cache: Any,
) -> None:
    with session_factory() as db:
        db.add(RuntimeModelProviderOverride(role="chat"))
        db.commit()

    calls: list[int] = []
    real = model_providers._load_override_rows

    def counting_load(settings: Any) -> dict[str, Any]:
        calls.append(1)
        return real(settings)

    monkeypatch.setattr(model_providers, "_load_override_rows", counting_load)

    load_settings()
    assert calls == [1]

    # The override rows changed but the env did not, so the env fingerprint is
    # unchanged; upsert must clear the cache so the next load re-reads the DB.
    settings = load_settings(apply_runtime_overrides=False)
    model_providers.upsert_provider_override(
        settings,
        role="chat",
        base_url="http://chat.example/v1",
        model="gpt-live",
    )
    refreshed = load_settings()
    assert calls == [1, 1]
    assert refreshed.model_providers.chat.base_url == "http://chat.example/v1"


def test_apply_runtime_overrides_false_is_uncached(
    session_factory: Any,
    monkeypatch: Any,
    clean_settings_cache: Any,
) -> None:
    # The db.py path rebuilds every call so a changed DATABASE_URL is honored.
    first = load_settings(apply_runtime_overrides=False)
    second = load_settings(apply_runtime_overrides=False)
    assert first is not second
    assert os.environ["DATABASE_URL"]
