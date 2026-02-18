from __future__ import annotations

import json

from app.services import queue as queue_mod


class _FakeRedis:
    def __init__(self):
        self.kv: dict[str, object] = {}
        self.list_values: dict[str, list[str]] = {}

    def get(self, key: str):
        return self.kv.get(key)

    def set(self, key: str, value):
        self.kv[key] = value

    def llen(self, key: str):
        return len(self.list_values.get(key, []))


def test_queue_stats_self_heals_stale_in_progress(monkeypatch):
    fake = _FakeRedis()
    fake.set(queue_mod.STATS_TOTAL, 7)
    fake.set(queue_mod.STATS_IN_PROGRESS, 1)
    fake.set(queue_mod.STATS_DONE, 7)
    fake.list_values[queue_mod.QUEUE_KEY] = []
    fake.set(queue_mod.WORKER_LOCK_KEY, None)
    fake.set(queue_mod.WORKER_HEARTBEAT_KEY, None)
    fake.set(
        queue_mod.RUNNING_TASK_KEY,
        json.dumps({"task": {"doc_id": 42, "task": "suggestions_vision"}, "started_at": 1}),
    )
    monkeypatch.setattr(queue_mod, "_get_client", lambda _settings: fake)

    stats = queue_mod.queue_stats(settings=object())  # type: ignore[arg-type]

    assert stats is not None
    assert stats["length"] == 0
    assert stats["in_progress"] == 0
    assert int(fake.get(queue_mod.STATS_IN_PROGRESS) or 0) == 0
