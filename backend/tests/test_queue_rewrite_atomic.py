from __future__ import annotations

import json
import threading
from typing import TYPE_CHECKING, Any, cast

from app.services.pipeline import queue as queue_mod

if TYPE_CHECKING:
    from app.config import Settings


class _AtomicRedis:
    """Fake redis whose `eval` runs each script atomically (one lock step),
    modeling Redis single-threaded Lua execution. `blpop`/`lrange`/`rpush`
    each take the lock, so a *non-atomic* lrange->delete->rpush sequence can
    interleave with a concurrent blpop, but an atomic eval cannot."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.lists: dict[str, list[str]] = {}
        self.sets: dict[str, set[str]] = {}
        self.kv: dict[str, object] = {}

    def rpush(self, key: str, *values: str) -> int:
        with self._lock:
            self.lists.setdefault(key, []).extend(values)
            return len(values)

    def lrange(self, key: str, start: int, end: int) -> list[str]:
        with self._lock:
            values = self.lists.get(key, [])
            return values if end == -1 else values[start : end + 1]

    def delete(self, key: str) -> int:
        with self._lock:
            return 1 if self.lists.pop(key, None) is not None else 0

    def sadd(self, key: str, *values: str) -> int:
        with self._lock:
            current = self.sets.setdefault(key, set())
            added = 0
            for value in values:
                if value not in current:
                    current.add(value)
                    added += 1
            return added

    def srem(self, key: str, *values: str) -> int:
        with self._lock:
            current = self.sets.get(key, set())
            removed = 0
            for value in values:
                if value in current:
                    current.discard(value)
                    removed += 1
            return removed

    def smembers(self, key: str) -> set[str]:
        with self._lock:
            return set(self.sets.get(key, set()))

    def clear(self) -> None:
        with self._lock:
            self.lists.clear()
            self.sets.clear()
            self.kv.clear()

    def lpop(self, key: str) -> str | None:
        with self._lock:
            values = self.lists.get(key)
            if not values:
                return None
            return values.pop(0)

    def get(self, key: str) -> object | None:
        with self._lock:
            return self.kv.get(key)

    def incr(self, key: str, amount: int = 1) -> int:
        with self._lock:
            raw = self.kv.get(key)
            value = raw if isinstance(raw, int) else 0
            value += amount
            self.kv[key] = value
            return value

    def blpop(self, key: str, timeout: int = 0) -> tuple[str, str] | None:
        with self._lock:
            values = self.lists.get(key)
            if not values:
                return None
            return (key, values.pop(0))

    def eval(self, script: str, numkeys: int, *keys_and_args: Any) -> object:
        key = keys_and_args[0]
        args = keys_and_args[1:]
        with self._lock:  # atomic: whole script is one unit
            if script is queue_mod._REORDER_QUEUE_LUA:
                items = self.lists.get(key, [])
                from_i, to_i = int(args[0]), int(args[1])
                if not items or from_i < 0 or from_i >= len(items):
                    return 0
                entry = items.pop(from_i)
                if to_i < 0:
                    to_i = 0
                if to_i > len(items):
                    to_i = len(items)
                items.insert(to_i, entry)
                self.lists[key] = items
                return 1
            if script is queue_mod._REMOVE_QUEUE_ITEM_LUA:
                items = self.lists.get(key, [])
                idx = int(args[0])
                if not items or idx < 0 or idx >= len(items):
                    return 0
                entry = items.pop(idx)
                self.lists[key] = items
                return entry
            if script is queue_mod._REQUEUE_DLQ_ITEM_LUA:
                items = self.lists.get(key, [])
                idx = int(args[0])
                if idx < 0 or idx >= len(items):
                    return None
                entry = items[idx]
                self.lists[key] = [v for i, v in enumerate(items) if i != idx]
                return entry
            raise AssertionError(f"unknown script: {script!r}")


def _settings() -> Any:
    return cast("Settings", object())


def _make_client(fake: _AtomicRedis, monkeypatch: Any) -> None:
    monkeypatch.setattr(queue_mod, "_get_client", lambda _settings: fake)


def test_reorder_queue_reorders_atomically(monkeypatch: Any) -> None:
    fake = _AtomicRedis()
    _make_client(fake, monkeypatch)
    for i in range(3):
        fake.rpush(queue_mod.QUEUE_KEY, json.dumps({"doc_id": i}))
    assert fake.lrange(queue_mod.QUEUE_KEY, 0, -1) == [
        json.dumps({"doc_id": 0}),
        json.dumps({"doc_id": 1}),
        json.dumps({"doc_id": 2}),
    ]
    assert queue_mod.reorder_queue(_settings(), 0, 2) is True
    assert fake.lrange(queue_mod.QUEUE_KEY, 0, -1) == [
        json.dumps({"doc_id": 1}),
        json.dumps({"doc_id": 2}),
        json.dumps({"doc_id": 0}),
    ]


def test_reorder_queue_invalid_index_returns_false(monkeypatch: Any) -> None:
    fake = _AtomicRedis()
    _make_client(fake, monkeypatch)
    fake.rpush(queue_mod.QUEUE_KEY, json.dumps({"doc_id": 0}))
    assert queue_mod.reorder_queue(_settings(), 5, 0) is False
    assert queue_mod.reorder_queue(_settings(), 0, 99) is True  # clamps to end
    assert queue_mod.reorder_queue(_settings(), -1, 0) is False


def test_reorder_queue_empty_returns_false(monkeypatch: Any) -> None:
    fake = _AtomicRedis()
    _make_client(fake, monkeypatch)
    assert queue_mod.reorder_queue(_settings(), 0, 0) is False


def test_remove_queue_item_removes_and_cleans_dedup(monkeypatch: Any) -> None:
    fake = _AtomicRedis()
    _make_client(fake, monkeypatch)
    task = {"doc_id": 7, "task": "suggestions_vision", "source": "paperless_ocr"}
    fake.rpush(queue_mod.QUEUE_KEY, json.dumps(task))
    fake.rpush(queue_mod.QUEUE_KEY, json.dumps({"doc_id": 8, "task": "sync"}))
    key = queue_mod.task_key(task)
    fake.sadd(queue_mod.QUEUE_SET, key)
    assert queue_mod.remove_queue_item(_settings(), 0) is True
    remaining = fake.lrange(queue_mod.QUEUE_KEY, 0, -1)
    assert remaining == [json.dumps({"doc_id": 8, "task": "sync"})]
    assert key not in fake.smembers(queue_mod.QUEUE_SET)


def test_remove_queue_item_invalid_index_returns_false(monkeypatch: Any) -> None:
    fake = _AtomicRedis()
    _make_client(fake, monkeypatch)
    fake.rpush(queue_mod.QUEUE_KEY, json.dumps({"doc_id": 0}))
    assert queue_mod.remove_queue_item(_settings(), 5) is False
    assert queue_mod.remove_queue_item(_settings(), -1) is False
    assert queue_mod.remove_queue_item(_settings(), 0) is True


def test_requeue_dead_letter_item_removes_and_requeues(monkeypatch: Any) -> None:
    fake = _AtomicRedis()
    _make_client(fake, monkeypatch)
    task = {"doc_id": 42, "task": "suggestions_vision", "retry_count": 3}
    dlq_entry = json.dumps({"task": task, "attempts": 3})
    fake.rpush(queue_mod.DLQ_KEY, dlq_entry)
    fake.rpush(queue_mod.DLQ_KEY, json.dumps({"task": {"doc_id": 43, "task": "sync"}, "attempts": 1}))
    assert queue_mod.requeue_dead_letter_item(_settings(), 0) is True
    # DLQ item removed, only the other entry remains
    assert fake.lrange(queue_mod.DLQ_KEY, 0, -1) == [
        json.dumps({"task": {"doc_id": 43, "task": "sync"}, "attempts": 1})
    ]
    # Re-queued with retry_count reset to 0
    requeued = json.loads(fake.lrange(queue_mod.QUEUE_KEY, 0, -1)[0])
    assert requeued["retry_count"] == 0
    assert requeued["doc_id"] == 42


def test_requeue_dead_letter_item_invalid_index_returns_false(monkeypatch: Any) -> None:
    fake = _AtomicRedis()
    _make_client(fake, monkeypatch)
    fake.rpush(queue_mod.DLQ_KEY, json.dumps({"task": {"doc_id": 1, "task": "sync"}}))
    assert queue_mod.requeue_dead_letter_item(_settings(), 5) is False
    assert queue_mod.requeue_dead_letter_item(_settings(), -1) is False


class _RaisingEval(_AtomicRedis):
    def eval(self, script: str, numkeys: int, *keys_and_args: Any) -> object:
        raise RuntimeError("redis unavailable")


def test_rewrite_helpers_handle_redis_errors(monkeypatch: Any) -> None:
    fake = _RaisingEval()
    _make_client(fake, monkeypatch)
    assert queue_mod.reorder_queue(_settings(), 0, 1) is False
    assert queue_mod.remove_queue_item(_settings(), 0) is False
    assert queue_mod.requeue_dead_letter_item(_settings(), 0) is False


def test_rewrite_helpers_return_false_without_client(monkeypatch: Any) -> None:
    monkeypatch.setattr(queue_mod, "_get_client", lambda _settings: None)
    assert queue_mod.reorder_queue(_settings(), 0, 1) is False
    assert queue_mod.remove_queue_item(_settings(), 0) is False
    assert queue_mod.requeue_dead_letter_item(_settings(), 0) is False


def test_reorder_and_remove_do_not_duplicate_or_lose_tasks_under_blpop(
    monkeypatch: Any,
) -> None:
    """Issue #116 verification plan: run the worker blpop loop in a thread while
    hammering reorder_queue / remove_queue_item; assert no task executes twice
    and no enqueued task is lost."""
    fake = _AtomicRedis()
    _make_client(fake, monkeypatch)
    n = 2000
    tasks = {json.dumps({"doc_id": i}) for i in range(n)}
    for payload in sorted(tasks):
        fake.rpush(queue_mod.QUEUE_KEY, payload)

    executed: list[str] = []
    executed_lock = threading.Lock()
    stop = threading.Event()
    seen = 0

    def worker() -> None:
        nonlocal seen
        while True:
            result = fake.blpop(queue_mod.QUEUE_KEY, timeout=0)
            if result is not None:
                with executed_lock:
                    executed.append(result[1])
                seen += 1
            elif stop.is_set() and not fake.lrange(queue_mod.QUEUE_KEY, 0, -1):
                break

    thread = threading.Thread(target=worker)
    thread.start()
    try:
        # Hammer the atomic rewrite helpers while the worker drains the queue.
        # A non-atomic snapshot->delete->rpush could re-insert a task the worker
        # just popped (duplicate) or drop one; the atomic eval must not.
        for _ in range(5000):
            queue_mod.reorder_queue(_settings(), 0, 1)
            queue_mod.remove_queue_item(_settings(), 0)
    finally:
        stop.set()
        thread.join(timeout=10)

    # No task executed twice (atomic rewrite can't re-insert a popped item).
    counts: dict[str, int] = {}
    for payload in executed:
        counts[payload] = counts.get(payload, 0) + 1
    assert all(c == 1 for c in counts.values()), {
        p: c for p, c in counts.items() if c > 1
    }
    # Every executed payload was one we enqueued (no phantom tasks).
    assert set(executed) <= tasks
