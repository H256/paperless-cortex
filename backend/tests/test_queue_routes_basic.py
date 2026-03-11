from __future__ import annotations

import importlib
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base


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
