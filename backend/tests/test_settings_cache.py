from __future__ import annotations

import os
import threading
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


def test_worker_reloads_external_provider_changes_before_each_task(
    session_factory: Any,
    monkeypatch: Any,
    clean_settings_cache: Any,
) -> None:
    from app import worker

    monkeypatch.setenv("QUEUE_ENABLED", "1")
    with session_factory() as db:
        db.add(RuntimeModelProviderOverride(role="vision", model="removed-vision-model"))
        db.commit()

    stop_event = threading.Event()
    selected_models = iter(["selected-vision-model", "next-vision-model"])
    consumed_models: list[str | None] = []

    class Queue:
        def blpop(self, _key: str, *, timeout: int) -> tuple[bytes, bytes]:
            # Simulate the API committing in another process: no local cache reset.
            with session_factory() as db:
                row = db.get(RuntimeModelProviderOverride, "vision")
                assert row is not None
                row.model = next(selected_models)
                db.commit()
            return b"queue", b'{"doc_id": 2252, "task": "vision_ocr"}'

    def execute_task(**kwargs: Any) -> dict[str, None]:
        consumed_models.append(kwargs["settings"].vision_model)
        if len(consumed_models) == 2:
            stop_event.set()
        return {
            "pending_retry_payload": None,
            "pending_retry_delay_seconds": None,
            "pending_dead_letter": None,
        }

    monkeypatch.setattr(worker, "configure_logging", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(worker, "_install_signal_handlers", lambda *_args: None)
    monkeypatch.setattr(
        worker, "acquire_worker_runtime",
        lambda *_args, **_kwargs: (Queue(), None, stop_event, threading.Event()),
    )
    monkeypatch.setattr(worker, "run_worker_iteration_gate", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(worker, "run_worker_queue_maintenance", lambda *_args: None)
    monkeypatch.setattr(worker, "handle_worker_cancel_request", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(worker, "mark_worker_task_start", lambda *_args: None)
    monkeypatch.setattr(worker, "SessionLocal", session_factory)
    monkeypatch.setattr(worker, "execute_worker_task", execute_task)
    monkeypatch.setattr(worker, "finalize_worker_task", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(worker, "shutdown_worker_runtime", lambda *_args, **_kwargs: None)

    worker.main()

    assert consumed_models == ["selected-vision-model", "next-vision-model"]
