from __future__ import annotations

from app.services import queue as queue_mod


class _RaisingRedis:
    def get(self, _key: str):
        raise RuntimeError("redis unavailable")


def test_is_cancel_requested_handles_redis_errors(monkeypatch):
    monkeypatch.setattr(queue_mod, "_get_client", lambda _settings: _RaisingRedis())

    assert queue_mod.is_cancel_requested(settings=object()) is False  # type: ignore[arg-type]


def test_is_paused_handles_redis_errors(monkeypatch):
    monkeypatch.setattr(queue_mod, "_get_client", lambda _settings: _RaisingRedis())

    assert queue_mod.is_paused(settings=object()) is False  # type: ignore[arg-type]
