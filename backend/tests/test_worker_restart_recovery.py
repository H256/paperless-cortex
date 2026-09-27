from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, Any, cast

from app.services.pipeline import queue as queue_mod
from app.services.pipeline.worker_queue_runtime import acquire_worker_runtime

if TYPE_CHECKING:
    from app.config import Settings


class _FakeRedis:
    """Minimal in-memory redis stand-in for the keys the worker uses."""

    def __init__(self) -> None:
        self.kv: dict[str, object] = {}
        self.lists: dict[str, list[str]] = {}
        self.sets: dict[str, set[str]] = {}
        self.sorted: dict[str, dict[str, float]] = {}
        self.existing: dict[str, bool] = {}

    def set(self, key: str, value: object, *, nx: bool = False, ex: int | None = None) -> bool:
        if nx and key in self.kv:
            return False
        self.kv[key] = value
        self.existing[key] = True
        return True

    def get(self, key: str) -> object | None:
        return self.kv.get(key)

    def delete(self, *keys: str) -> int:
        removed = 0
        for key in keys:
            if key in self.kv:
                del self.kv[key]
                self.existing[key] = False
                removed += 1
            self.lists.pop(key, None)
            self.sets.pop(key, None)
            self.sorted.pop(key, None)
        return removed

    def exists(self, key: str) -> int:
        return 1 if key in self.existing else 0

    def ttl(self, key: str) -> int:
        return 300 if key in self.existing else -2

    def rpush(self, key: str, *values: str) -> int:
        self.lists.setdefault(key, []).extend(values)
        return len(values)

    def lrange(self, key: str, start: int, end: int) -> list[str]:
        values = self.lists.get(key, [])
        return values if end == -1 else values[start : end + 1]

    def sadd(self, key: str, *values: str) -> int:
        current = self.sets.setdefault(key, set())
        added = 0
        for value in values:
            if value not in current:
                current.add(value)
                added += 1
        return added

    def srem(self, key: str, *values: str) -> int:
        current = self.sets.get(key, set())
        removed = 0
        for value in values:
            if value in current:
                current.discard(value)
                removed += 1
        return removed

    def smembers(self, key: str) -> set[str]:
        return set(self.sets.get(key, set()))

    def zadd(self, key: str, mapping: dict[str, float]) -> int:
        self.sorted.setdefault(key, {}).update(mapping)
        return len(mapping)

    def zrange(self, key: str, start: int, end: int, *, withscores: bool = False) -> list:
        items = sorted(self.sorted.get(key, {}).items())
        if end != -1:
            items = items[start : end + 1]
        if withscores:
            return items
        return [member for member, _ in items]


def _settings() -> Any:
    return cast("Settings", object())


def _crashed_inflight_state(fake: _FakeRedis, now: int) -> None:
    """Redis state as left by a worker that died mid-task: the task was popped
    (blpop) so its payload is in neither queue, but its dedup member survives
    in QUEUE_SET and the running-task marker is still set."""
    task = {"doc_id": 42, "task": "suggestions_vision", "source": "paperless_ocr"}
    fake.sets[queue_mod.QUEUE_SET] = {queue_mod.task_key(task)}
    fake.set(
        queue_mod.RUNNING_TASK_KEY,
        json.dumps({"task": task, "started_at": now - 120}),
    )
    fake.set(queue_mod.WORKER_HEARTBEAT_KEY, now - 120)  # stale (TTL 30)
    fake.set(queue_mod.WORKER_LOCK_KEY, None)


def test_worker_restart_requeues_crashed_inflight_task(monkeypatch: Any) -> None:
    fake = _FakeRedis()
    now = int(time.time())
    _crashed_inflight_state(fake, now)
    monkeypatch.setattr(queue_mod, "_get_client", lambda _settings: fake)

    recovered = queue_mod.recover_inflight_dedup_keys(_settings())

    assert recovered == 1
    assert fake.lrange(queue_mod.QUEUE_KEY, 0, -1) == [
        json.dumps({"doc_id": 42, "task": "suggestions_vision", "source": "paperless_ocr"})
    ]
    # The dedup member stays (finalize srem's it when the task completes), so a
    # re-enqueue of the same task is deduplicated, not double-queued.
    assert queue_mod.task_key({"doc_id": 42, "task": "suggestions_vision", "source": "paperless_ocr"}) in fake.smembers(
        queue_mod.QUEUE_SET
    )


def test_worker_restart_recovery_preserves_original_task_payload(monkeypatch: Any) -> None:
    fake = _FakeRedis()
    now = int(time.time())
    task = {
        "doc_id": 7,
        "task": "cleanup_texts",
        "source": "vision_ocr",
        "clear_first": True,
    }
    fake.sets[queue_mod.QUEUE_SET] = {queue_mod.task_key(task)}
    fake.set(queue_mod.RUNNING_TASK_KEY, json.dumps({"task": task, "started_at": now - 120}))
    fake.set(queue_mod.WORKER_HEARTBEAT_KEY, now - 120)
    monkeypatch.setattr(queue_mod, "_get_client", lambda _settings: fake)

    recovered = queue_mod.recover_inflight_dedup_keys(_settings())

    assert recovered == 1
    requeued = json.loads(fake.lrange(queue_mod.QUEUE_KEY, 0, -1)[0])
    assert requeued == task  # original payload, not a key-reconstructed one


def test_worker_restart_recovery_reconstructs_task_when_marker_gone(monkeypatch: Any) -> None:
    fake = _FakeRedis()
    now = int(time.time())
    # Marker lost (e.g. cleared by an earlier restart) but dedup member survives.
    fake.sets[queue_mod.QUEUE_SET] = {
        "9:cleanup_texts:vision_ocr:note",
        "12:full",
    }
    fake.set(queue_mod.WORKER_HEARTBEAT_KEY, now - 120)
    monkeypatch.setattr(queue_mod, "_get_client", lambda _settings: fake)

    recovered = queue_mod.recover_inflight_dedup_keys(_settings())

    assert recovered == 2
    payloads = [json.loads(entry) for entry in fake.lrange(queue_mod.QUEUE_KEY, 0, -1)]
    assert {"doc_id": 9, "task": "cleanup_texts", "source": "vision_ocr", "field": "note"} in payloads
    assert {"doc_id": 12, "task": "full"} in payloads


def test_worker_restart_recovery_skips_healthy_queued_and_delayed_tasks(monkeypatch: Any) -> None:
    fake = _FakeRedis()
    now = int(time.time())
    queued_task = {"doc_id": 5, "task": "sync"}
    delayed_task = {"doc_id": 6, "task": "suggestions_paperless"}
    fake.sets[queue_mod.QUEUE_SET] = {
        queue_mod.task_key(queued_task),
        queue_mod.task_key(delayed_task),
    }
    fake.rpush(queue_mod.QUEUE_KEY, json.dumps(queued_task))
    fake.zadd(queue_mod.DELAYED_QUEUE_KEY, {json.dumps(delayed_task): now + 30})
    fake.set(queue_mod.WORKER_HEARTBEAT_KEY, now - 120)
    monkeypatch.setattr(queue_mod, "_get_client", lambda _settings: fake)

    recovered = queue_mod.recover_inflight_dedup_keys(_settings())

    assert recovered == 0
    assert fake.lrange(queue_mod.QUEUE_KEY, 0, -1) == [json.dumps(queued_task)]
    assert len(fake.zrange(queue_mod.DELAYED_QUEUE_KEY, 0, -1)) == 1


def test_worker_restart_recovery_skips_while_previous_worker_heartbeat_fresh(
    monkeypatch: Any,
) -> None:
    fake = _FakeRedis()
    now = int(time.time())
    _crashed_inflight_state(fake, now)
    fake.set(queue_mod.WORKER_HEARTBEAT_KEY, now)  # fresh: previous worker alive
    monkeypatch.setattr(queue_mod, "_get_client", lambda _settings: fake)

    recovered = queue_mod.recover_inflight_dedup_keys(_settings())

    assert recovered == 0
    assert fake.lrange(queue_mod.QUEUE_KEY, 0, -1) == []


def test_worker_restart_recovery_is_noop_without_dedup_members(monkeypatch: Any) -> None:
    fake = _FakeRedis()
    fake.set(queue_mod.WORKER_HEARTBEAT_KEY, int(time.time()) - 120)
    monkeypatch.setattr(queue_mod, "_get_client", lambda _settings: fake)

    assert queue_mod.recover_inflight_dedup_keys(_settings()) == 0


def test_acquire_worker_runtime_runs_inflight_recovery(monkeypatch: Any) -> None:
    from app.services.pipeline import worker_queue_runtime as runtime_mod

    calls: list[str] = []
    fake = _FakeRedis()
    fake.set(queue_mod.WORKER_LOCK_KEY, "w:1")
    fake.set(queue_mod.WORKER_HEARTBEAT_KEY, int(time.time()) - 120)

    monkeypatch.setattr(runtime_mod, "_get_client", lambda _settings: fake)
    monkeypatch.setattr(
        runtime_mod, "acquire_worker_lock", lambda _settings, _token: calls.append("acquire") or True
    )
    monkeypatch.setattr(runtime_mod, "clear_running_task", lambda _settings: calls.append("clear"))
    monkeypatch.setattr(
        runtime_mod, "recover_inflight_dedup_keys", lambda _settings: calls.append("recover")
    )
    monkeypatch.setattr(runtime_mod, "refresh_worker_lock", lambda _settings, _token: True)
    monkeypatch.setattr(runtime_mod, "mark_worker_heartbeat", lambda _settings: None)

    class _FakeSettings:
        redis_host = "redis://localhost"

    client, _ctx, stop_event, _lock_lost = acquire_worker_runtime(
        _FakeSettings(),
        worker_token="w:1",
        heartbeat_interval_seconds=30,
        logger=logging.getLogger(__name__),
    )

    stop_event.set()
    assert client is fake
    assert calls.index("recover") < calls.index("clear")
    assert "acquire" in calls


def test_recovered_task_is_consumed_by_worker_blpop_contract(monkeypatch: Any) -> None:
    """End-to-end: a crashed task is re-queued and the worker's blpop path
    (parse_worker_queue_item) accepts the re-queued payload."""
    from app.services.pipeline.worker_runtime import parse_worker_queue_item

    fake = _FakeRedis()
    now = int(time.time())
    _crashed_inflight_state(fake, now)
    monkeypatch.setattr(queue_mod, "_get_client", lambda _settings: fake)

    queue_mod.recover_inflight_dedup_keys(_settings())

    payload = fake.lrange(queue_mod.QUEUE_KEY, 0, -1)[0]
    parsed = parse_worker_queue_item(
        payload,
        log_fn=lambda *_args, **_kwargs: None,
        logger=logging.getLogger(__name__),
    )
    assert parsed is not None
    assert parsed["doc_id"] == 42
    assert parsed["task_type"] == "suggestions_vision"
    assert parsed["task_payload"]["source"] == "paperless_ocr"
