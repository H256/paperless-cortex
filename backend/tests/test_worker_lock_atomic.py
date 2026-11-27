from __future__ import annotations

from typing import Any, cast

from redis.exceptions import ResponseError

from app.services.pipeline import queue as queue_mod


class _LockRedis:
    """Fake whose `eval` models the two lock scripts (compare, then act)."""

    def __init__(self, owner: str | None) -> None:
        self.owner = owner
        self.ttl: int | None = None

    def eval(self, script: str, _numkeys: int, _key: str, token: str, *rest: Any) -> int:
        if self.owner != token:
            return 0
        if script is queue_mod._REFRESH_LOCK_LUA:
            self.ttl = int(rest[0])
            return 1
        assert script is queue_mod._RELEASE_LOCK_LUA
        self.owner = None
        return 1

    def get(self, _key: str) -> None:  # the old non-atomic path must not be used
        raise AssertionError("lock must be checked inside the script, not via GET")


def _use(monkeypatch: Any, client: Any) -> Any:
    monkeypatch.setattr(queue_mod, "_get_client", lambda _settings: client)
    return cast("Any", object())


def test_refresh_only_extends_own_lock(monkeypatch: Any) -> None:
    client = _LockRedis("me")
    settings = _use(monkeypatch, client)
    assert queue_mod.refresh_worker_lock(settings, "me") is True
    assert client.ttl == queue_mod.WORKER_LOCK_TTL
    assert queue_mod.refresh_worker_lock(settings, "someone-else") is False


def test_release_only_deletes_own_lock(monkeypatch: Any) -> None:
    client = _LockRedis("me")
    settings = _use(monkeypatch, client)
    queue_mod.release_worker_lock(settings, "someone-else")
    assert client.owner == "me"
    queue_mod.release_worker_lock(settings, "me")
    assert client.owner is None


def test_redis_errors_are_swallowed(monkeypatch: Any) -> None:
    class _Broken:
        def eval(self, *_a: Any, **_k: Any) -> Any:
            raise ResponseError("boom")

    settings = _use(monkeypatch, _Broken())
    assert queue_mod.refresh_worker_lock(settings, "me") is False
    queue_mod.release_worker_lock(settings, "me")
