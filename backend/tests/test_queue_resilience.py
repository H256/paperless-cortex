from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from app.services.pipeline import queue as queue_mod

if TYPE_CHECKING:
    from app.config import Settings


class _RaisingRedis:
    def get(self, _key: str) -> str:
        raise RuntimeError("redis unavailable")


def test_is_cancel_requested_handles_redis_errors(monkeypatch: Any) -> None:
    monkeypatch.setattr(queue_mod, "_get_client", lambda _settings: _RaisingRedis())

    assert queue_mod.is_cancel_requested(settings=cast("Settings", object())) is False


def test_is_paused_handles_redis_errors(monkeypatch: Any) -> None:
    monkeypatch.setattr(queue_mod, "_get_client", lambda _settings: _RaisingRedis())

    assert queue_mod.is_paused(settings=cast("Settings", object())) is False
