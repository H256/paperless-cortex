from __future__ import annotations

import importlib
import os
import tempfile
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.services.pipeline import queue

if TYPE_CHECKING:
    from app.config import Settings


def _build_api_client(queue_enabled: bool) -> Any:
    db_path = Path(tempfile.gettempdir()) / f"paperless_intelligence_test_{uuid.uuid4().hex}.db"
    os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{db_path}"
    os.environ["QUEUE_ENABLED"] = "1" if queue_enabled else "0"

    import app.main as main

    importlib.reload(main)

    engine = create_engine(
        os.environ["DATABASE_URL"],
        connect_args={"check_same_thread": False},
    )
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    from app.db import get_db

    def override_get_db() -> Any:
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    main.api.dependency_overrides[get_db] = override_get_db

    from fastapi.testclient import TestClient

    return TestClient(main.api)


def test_queue_status_disabled_returns_stub_payload() -> None:
    client = _build_api_client(queue_enabled=False)

    response = client.get("/queue/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is False
    assert payload["length"] is None
    assert payload["paused"] is False


def test_queue_status_enabled_uses_stats(api_client: Any, monkeypatch: Any) -> None:
    import app.routes.queue as queue_routes

    monkeypatch.setenv("QUEUE_ENABLED", "1")
    monkeypatch.setattr(
        queue_routes,
        "queue_stats",
        lambda _settings: {"length": 3, "total": 10, "in_progress": 1, "done": 6},
    )
    monkeypatch.setattr(queue_routes, "is_paused", lambda _settings: True)

    response = api_client.get("/queue/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is True
    assert payload["length"] == 3
    assert payload["total"] == 10
    assert payload["in_progress"] == 1
    assert payload["done"] == 6
    assert payload["paused"] is True
    assert "last_run_seconds" in payload
    assert "last_run_at" in payload


def test_queue_enqueue_enabled_returns_count(api_client: Any, monkeypatch: Any) -> None:
    import app.routes.queue as queue_routes

    monkeypatch.setenv("QUEUE_ENABLED", "1")
    monkeypatch.setattr(queue_routes, "enqueue_docs", lambda _settings, doc_ids: len(doc_ids))

    response = api_client.post("/queue/enqueue", json={"doc_ids": [1, 2, 3]})
    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is True
    assert payload["enqueued"] == 3


def test_resume_queue_clears_pause_and_cancel_markers(monkeypatch: Any) -> None:
    import app.services.pipeline.queue as queue

    class Client:
        def __init__(self) -> None:
            self.deleted: list[tuple[str, ...]] = []

        def delete(self, *keys: str) -> None:
            self.deleted.append(keys)

    client = Client()
    monkeypatch.setattr(queue, "_get_client", lambda _settings: client)

    queue.resume_queue(cast("Settings", object()))

    assert client.deleted == [(queue.PAUSE_KEY, queue.CANCEL_KEY)]


class _Pipeline:
    def __init__(self, fake: _FakeQueueRedis) -> None:
        self._fake = fake
        self._ops: list[tuple[str, ...]] = []

    def sadd(self, key: str, value: str) -> None:
        self._ops.append(("sadd", key, value))

    def rpush(self, key: str, value: str) -> None:
        self._ops.append(("rpush", key, value))

    def incr(self, key: str) -> None:
        self._ops.append(("incr", key))

    def execute(self) -> list[int]:
        results: list[int] = []
        for op in self._ops:
            if op[0] == "sadd":
                members = self._fake.sets.setdefault(op[1], set())
                results.append(0 if op[2] in members else 1)
                members.add(op[2])
            elif op[0] == "incr":
                current = int(self._fake.kv.get(op[1], 0)) + 1
                self._fake.kv[op[1]] = str(current)
                results.append(current)
            else:
                values = self._fake.lists.setdefault(op[1], [])
                values.append(op[2])
                results.append(len(values))
        self._ops = []
        return results


class _FakeQueueRedis:
    def __init__(self) -> None:
        self.kv: dict[str, str] = {queue.PAUSE_KEY: "1", queue.CANCEL_KEY: "1"}
        self.sets: dict[str, set[str]] = {}
        self.lists: dict[str, list[str]] = {}

    def get(self, key: str) -> str | None:
        return self.kv.get(key)

    def delete(self, *keys: str) -> int:
        removed = 0
        for key in keys:
            if key in self.kv:
                del self.kv[key]
                removed += 1
        return removed

    def pipeline(self) -> _Pipeline:
        return _Pipeline(self)


def test_resume_queue_clears_stale_cancel_marker_and_reenables_enqueue(
    monkeypatch: Any,
) -> None:
    import app.services.pipeline.queue as queue

    fake = _FakeQueueRedis()
    monkeypatch.setattr(queue, "_get_client", lambda _settings: fake)
    settings = cast("Settings", object())
    task = [{"doc_id": 7, "task": "sync"}]

    # Stale cancel marker (no healthy worker to consume it) blocks enqueues.
    assert queue.is_cancel_requested(settings) is True
    assert queue.enqueue_task_sequence(settings, task) == 0

    queue.resume_queue(settings)

    assert fake.get(queue.CANCEL_KEY) is None
    assert queue.is_cancel_requested(settings) is False
    assert queue.enqueue_task_sequence(settings, task) == 1


def test_queue_worker_lock_route_returns_status(api_client: Any, monkeypatch: Any) -> None:
    import app.routes.queue as queue_routes

    monkeypatch.setenv("QUEUE_ENABLED", "1")
    monkeypatch.setattr(
        queue_routes,
        "worker_lock_status",
        lambda _settings: {"has_lock": True, "owner": "worker:test", "ttl_seconds": 42},
    )

    response = api_client.get("/queue/worker-lock")
    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is True
    assert payload["has_lock"] is True
    assert payload["owner"] == "worker:test"
    assert payload["ttl_seconds"] == 42


def test_queue_running_route_returns_task_payload(api_client: Any, monkeypatch: Any) -> None:
    import app.routes.queue as queue_routes

    monkeypatch.setenv("QUEUE_ENABLED", "1")
    monkeypatch.setattr(
        queue_routes,
        "get_running_task",
        lambda _settings: {
            "task": {"doc_id": 22, "task": "sync"},
            "started_at": 1741687200,
        },
    )

    response = api_client.get("/queue/running")
    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is True
    assert payload["task"]["doc_id"] == 22
    assert payload["task"]["task"] == "sync"
    assert "raw" in payload["task"]
    assert payload["started_at"] == 1741687200
