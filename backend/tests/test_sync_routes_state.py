from __future__ import annotations

import os
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import SyncState


def _insert_sync_state(
    key: str,
    *,
    status: str = "running",
    processed: int = 0,
    total: int = 0,
    started_at: str | None = None,
    last_synced_at: str | None = None,
    cancel_requested: bool = False,
) -> None:
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(
            SyncState(
                key=key,
                status=status,
                processed=processed,
                total=total,
                started_at=started_at,
                last_synced_at=last_synced_at,
                cancel_requested=cancel_requested,
            )
        )
        db.commit()


def test_sync_status_returns_idle_without_state(api_client: Any) -> None:
    response = api_client.get("/sync/documents")
    assert response.status_code == 200
    assert response.json() == {
        "last_synced_at": None,
        "status": "idle",
        "processed": 0,
        "total": 0,
        "started_at": None,
        "cancel_requested": None,
        "eta_seconds": None,
    }


def test_sync_cancel_marks_state(api_client: Any) -> None:
    _insert_sync_state("documents", status="running", processed=1, total=4)

    response = api_client.post("/sync/documents/cancel")
    assert response.status_code == 200
    assert response.json()["status"] == "cancelling"

    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        state = db.get(SyncState, "documents")
        assert state is not None
        assert state.cancel_requested is True


def test_sync_document_priority_queues_front(api_client: Any, monkeypatch: Any) -> None:
    import app.routes.sync as sync_routes

    monkeypatch.setenv("QUEUE_ENABLED", "1")

    monkeypatch.setattr(
        sync_routes.paperless,
        "get_document",
        lambda _settings, doc_id: {
            "id": doc_id,
            "title": "Queued Sync Doc",
            "content": "content",
            "correspondent": None,
            "document_type": None,
            "document_date": None,
            "created": "2026-03-11T10:00:00+00:00",
            "modified": "2026-03-11T10:00:00+00:00",
            "added": None,
            "deleted_at": None,
            "archive_serial_number": None,
            "original_file_name": None,
            "mime_type": None,
            "page_count": 1,
            "owner": None,
            "user_can_change": True,
            "is_shared_by_requester": False,
            "notes": [],
            "tags": [],
        },
    )
    monkeypatch.setattr(
        sync_routes,
        "build_task_sequence",
        lambda _settings, doc_id, include_sync, force: [
            {"doc_id": doc_id, "task": "embeddings_paperless"}
        ],
    )

    queued_front: list[dict[str, Any]] = []
    queued_normal: list[dict[str, Any]] = []

    def _enqueue_front(_settings: Any, tasks: list[dict[str, Any]], *, force: bool = False) -> None:
        queued_front.extend(tasks)
        assert force is True

    def _enqueue_normal(_settings: Any, tasks: list[dict[str, Any]]) -> None:
        queued_normal.extend(tasks)

    monkeypatch.setattr(sync_routes, "enqueue_task_sequence_front", _enqueue_front)
    monkeypatch.setattr(sync_routes, "enqueue_task_sequence", _enqueue_normal)

    response = api_client.post(
        "/sync/documents/911",
        params={"embed": True, "priority": True},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload == {"id": 911, "status": "synced", "embedded": 0}
    assert queued_front == [{"doc_id": 911, "task": "embeddings_paperless"}]
    assert queued_normal == []
