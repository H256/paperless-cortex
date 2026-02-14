from __future__ import annotations

import importlib
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, TaskRun


def _build_api_client(queue_enabled: bool):
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

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    main.api.dependency_overrides[get_db] = override_get_db

    from fastapi.testclient import TestClient

    return TestClient(main.api), testing_session_local


def test_queue_task_runs_disabled_returns_empty():
    client, _session_factory = _build_api_client(queue_enabled=False)
    response = client.get("/queue/task-runs")
    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is False
    assert payload["count"] == 0
    assert payload["items"] == []
    error_types_response = client.get("/queue/error-types")
    assert error_types_response.status_code == 200
    error_types_payload = error_types_response.json()
    assert error_types_payload["enabled"] is False
    assert error_types_payload["items"] == []


def test_queue_task_runs_lists_rows():
    client, session_factory = _build_api_client(queue_enabled=True)
    with session_factory() as db:
        db.add(
            TaskRun(
                doc_id=1756,
                task="embeddings_vision",
                source="vision_ocr",
                status="failed",
                worker_id="worker:test",
                attempt=1,
                error_type="EMBED_CONTEXT_OVERFLOW",
                error_message="request exceeds context",
                started_at="2026-02-12T10:00:00+00:00",
                finished_at="2026-02-12T10:00:01+00:00",
                duration_ms=1000,
                created_at="2026-02-12T10:00:00+00:00",
                updated_at="2026-02-12T10:00:01+00:00",
            )
        )
        db.commit()

    response = client.get("/queue/task-runs?doc_id=1756&status=failed")
    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is True
    assert payload["count"] == 1
    assert len(payload["items"]) == 1
    item = payload["items"][0]
    assert item["doc_id"] == 1756
    assert item["task"] == "embeddings_vision"
    assert item["status"] == "failed"
    assert item["error_type"] == "EMBED_CONTEXT_OVERFLOW"
    assert item["error_retryable"] is False
    assert item["error_category"] == "embedding"


def test_queue_task_runs_ignores_invalid_checkpoint_json():
    client, session_factory = _build_api_client(queue_enabled=True)
    with session_factory() as db:
        db.add(
            TaskRun(
                doc_id=1800,
                task="vision_ocr",
                source="vision_ocr",
                status="running",
                worker_id="worker:test",
                attempt=1,
                checkpoint_json="{invalid-json",
                started_at="2026-02-12T10:00:00+00:00",
                finished_at=None,
                duration_ms=None,
                created_at="2026-02-12T10:00:00+00:00",
                updated_at="2026-02-12T10:00:00+00:00",
            )
        )
        db.commit()

    response = client.get("/queue/task-runs?doc_id=1800&status=running")
    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is True
    assert payload["count"] == 1
    assert len(payload["items"]) == 1
    assert payload["items"][0]["checkpoint"] is None


def test_queue_task_runs_supports_text_query_filter():
    client, session_factory = _build_api_client(queue_enabled=True)
    with session_factory() as db:
        db.add(
            TaskRun(
                doc_id=1900,
                task="embeddings_vision",
                source="vision_ocr",
                status="failed",
                worker_id="worker:test",
                attempt=1,
                error_type="EMBED_CONTEXT_OVERFLOW",
                error_message="overflow fallback split parts=3",
                started_at="2026-02-12T10:00:00+00:00",
                finished_at="2026-02-12T10:00:01+00:00",
                duration_ms=1000,
                created_at="2026-02-12T10:00:00+00:00",
                updated_at="2026-02-12T10:00:01+00:00",
            )
        )
        db.add(
            TaskRun(
                doc_id=1901,
                task="suggestions_paperless",
                source="paperless_ocr",
                status="done",
                worker_id="worker:test",
                attempt=1,
                started_at="2026-02-12T10:01:00+00:00",
                finished_at="2026-02-12T10:01:01+00:00",
                duration_ms=1000,
                created_at="2026-02-12T10:01:00+00:00",
                updated_at="2026-02-12T10:01:01+00:00",
            )
        )
        db.commit()

    response = client.get("/queue/task-runs?q=overflow")
    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is True
    assert payload["count"] == 1
    assert len(payload["items"]) == 1
    assert payload["items"][0]["doc_id"] == 1900


def test_queue_error_types_lists_catalog():
    client, _session_factory = _build_api_client(queue_enabled=True)
    response = client.get("/queue/error-types")
    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is True
    items = payload["items"]
    assert isinstance(items, list)
    assert any(item["code"] == "LLM_TIMEOUT" and item["retryable"] is True for item in items)
    assert any(item["code"] == "INVALID_MODEL_OUTPUT" and item["retryable"] is False for item in items)


def test_queue_task_runs_skips_malformed_rows(monkeypatch):
    client, _session_factory = _build_api_client(queue_enabled=True)

    import app.routes.queue as queue_routes

    malformed_row = SimpleNamespace(
        id="not-an-int",
        doc_id=1756,
        task="sync",
        source=None,
        status="done",
        worker_id=None,
        attempt=1,
        checkpoint_json=None,
        error_type=None,
        error_message=None,
        started_at=None,
        finished_at=None,
        duration_ms=None,
        created_at=None,
        updated_at=None,
    )
    monkeypatch.setattr(queue_routes, "list_task_runs", lambda *args, **kwargs: (1, [malformed_row]))

    response = client.get("/queue/task-runs")
    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is True
    assert payload["count"] == 1
    assert payload["items"] == []
