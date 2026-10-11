from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from app.services.pipeline import queue as queue_mod
from app.services.pipeline.worker_queue_runtime import finalize_worker_task

if TYPE_CHECKING:
    from app.config import Settings

# Capture the builtin `set` at module scope (the fake redis class defines a
# method named `set` that would otherwise shadow the builtin in annotations).
_builtins_set = set


def _settings() -> Any:
    return cast("Settings", object())


class _StatsFakeRedis:
    """In-memory redis stand-in covering the client methods used by
    finalize_worker_task and the counter helpers it drives."""

    def __init__(self) -> None:
        self.kv: dict[str, object] = {}
        self.lists: dict[str, list[str]] = {}
        self.sets: dict[str, set[str]] = {}
        self.sorted: dict[str, dict[str, float]] = {}

    def set(self, key: str, value: object, *, nx: bool = False, ex: int | None = None) -> bool:
        self.kv[key] = value
        return True

    def get(self, key: str) -> object | None:
        return self.kv.get(key)

    def intval(self, key: str) -> int:
        raw = self.kv.get(key)
        return raw if isinstance(raw, int) else 0

    def delete(self, *keys: str) -> int:
        removed = 0
        for key in keys:
            if key in self.kv:
                del self.kv[key]
                removed += 1
            self.lists.pop(key, None)
            self.sets.pop(key, None)
            self.sorted.pop(key, None)
        return removed

    def incr(self, key: str) -> int:
        raw = self.kv.get(key)
        current = int(raw) if isinstance(raw, int) else 0
        self.kv[key] = current + 1
        return current + 1

    def rpush(self, key: str, *values: str) -> int:
        self.lists.setdefault(key, []).extend(values)
        return len(values)

    def lpush(self, key: str, *values: str) -> int:
        self.lists.setdefault(key, []).extend(reversed(values))
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

    def smembers(self, key: str) -> _builtins_set[str]:
        return set(self.sets.get(key, set()))

    def zadd(self, key: str, mapping: dict[str, float]) -> int:
        self.sorted.setdefault(key, {}).update(mapping)
        return len(mapping)


def _finalize(
    fake: _StatsFakeRedis,
    *,
    monkeypatch: Any,
    task: dict[str, object] | None,
    doc_id: int,
    pending_retry_payload: dict[str, object] | None,
    pending_retry_delay_seconds: int | None,
    pending_dead_letter: dict[str, object] | None,
) -> None:
    settings = _settings()
    monkeypatch.setattr(queue_mod, "_get_client", lambda _s: fake)
    finalize_worker_task(
        settings,
        client=fake,
        task=task,
        doc_id=doc_id,
        run_started=0.0,
        pending_retry_payload=pending_retry_payload,
        pending_retry_delay_seconds=pending_retry_delay_seconds,
        pending_dead_letter=pending_dead_letter,
    )


def test_finalize_retry_does_not_increment_done(monkeypatch: Any) -> None:
    fake = _StatsFakeRedis()
    fake.set(queue_mod.STATS_IN_PROGRESS, 1)
    fake.set(queue_mod.STATS_DONE, 0)
    fake.set(queue_mod.STATS_TOTAL, 1)
    task = {"doc_id": 42, "task": "suggestions_vision", "source": "paperless_ocr"}
    fake.sets[queue_mod.QUEUE_SET] = {queue_mod.task_key(task)}

    _finalize(
        fake,
        monkeypatch=monkeypatch,
        task=task,
        doc_id=42,
        pending_retry_payload=task,
        pending_retry_delay_seconds=5,
        pending_dead_letter=None,
    )

    # Retried task is not terminal: done stays 0, in_progress slot released,
    # and the task is re-enqueued delayed (not counted as done).
    assert fake.intval(queue_mod.STATS_DONE) == 0
    assert fake.intval(queue_mod.STATS_IN_PROGRESS) == 0
    assert len(fake.sorted.get(queue_mod.DELAYED_QUEUE_KEY, {})) == 1


def test_finalize_success_increments_done(monkeypatch: Any) -> None:
    fake = _StatsFakeRedis()
    fake.set(queue_mod.STATS_IN_PROGRESS, 1)
    fake.set(queue_mod.STATS_DONE, 0)
    fake.set(queue_mod.STATS_TOTAL, 1)
    task = {"doc_id": 42, "task": "suggestions_vision", "source": "paperless_ocr"}
    fake.sets[queue_mod.QUEUE_SET] = {queue_mod.task_key(task)}

    _finalize(
        fake,
        monkeypatch=monkeypatch,
        task=task,
        doc_id=42,
        pending_retry_payload=None,
        pending_retry_delay_seconds=None,
        pending_dead_letter=None,
    )

    assert fake.intval(queue_mod.STATS_DONE) == 1
    assert fake.intval(queue_mod.STATS_IN_PROGRESS) == 0


def test_finalize_dead_letter_increments_done(monkeypatch: Any) -> None:
    fake = _StatsFakeRedis()
    fake.set(queue_mod.STATS_IN_PROGRESS, 1)
    fake.set(queue_mod.STATS_DONE, 0)
    fake.set(queue_mod.STATS_TOTAL, 1)
    task = {"doc_id": 42, "task": "suggestions_vision", "source": "paperless_ocr"}
    fake.sets[queue_mod.QUEUE_SET] = {queue_mod.task_key(task)}

    _finalize(
        fake,
        monkeypatch=monkeypatch,
        task=task,
        doc_id=42,
        pending_retry_payload=None,
        pending_retry_delay_seconds=None,
        pending_dead_letter={
            "task": task,
            "error_type": "WORKER_TASK_ERROR",
            "error_message": "boom",
            "attempt": 3,
        },
    )

    # Dead-lettered task is terminal: counted as done and recorded in the DLQ.
    assert fake.intval(queue_mod.STATS_DONE) == 1
    assert fake.intval(queue_mod.STATS_IN_PROGRESS) == 0
    assert len(fake.lists.get(queue_mod.DLQ_KEY, [])) == 1
