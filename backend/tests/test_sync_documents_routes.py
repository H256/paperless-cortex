from __future__ import annotations

import os
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Document, SyncState


def _insert_local_document(doc_id: int, title: str) -> None:
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(
            Document(
                id=doc_id,
                title=title,
                created="2026-03-11T10:00:00+00:00",
                modified="2026-03-11T10:00:00+00:00",
            )
        )
        db.commit()


def test_sync_documents_marks_missing_and_queues_embed_followups(
    api_client: Any, monkeypatch: Any
) -> None:
    import app.routes.sync as sync_routes

    _insert_local_document(1001, "Missing Local Doc")
    monkeypatch.setenv("QUEUE_ENABLED", "1")

    queued: list[list[dict[str, object]]] = []

    monkeypatch.setattr(
        sync_routes.paperless,
        "list_documents",
        lambda _settings, page, page_size, modified__gte=None: {
            "count": 1,
            "next": None,
            "results": [
                {
                    "id": 1002,
                    "title": "Remote Synced Doc",
                    "content": "remote content",
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
                }
            ],
        },
    )
    monkeypatch.setattr(
        sync_routes,
        "build_task_sequence",
        lambda _settings, doc_id, include_sync, force: [
            {"doc_id": doc_id, "task": "embeddings_paperless"}
        ],
    )

    def _enqueue_task_sequence(_settings: Any, tasks: list[dict[str, object]]) -> int:
        queued.append(list(tasks))
        return len(tasks)

    monkeypatch.setattr(sync_routes, "enqueue_task_sequence", _enqueue_task_sequence)

    response = api_client.post(
        "/sync/documents",
        params={
            "incremental": False,
            "embed": True,
            "mark_missing": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["upserted"] == 1
    assert payload["incremental"] is False
    assert payload["embedded"] == 0
    assert payload["marked_deleted"] == 1
    assert queued == [[{"doc_id": 1002, "task": "embeddings_paperless"}]]

    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        missing = db.get(Document, 1001)
        synced = db.get(Document, 1002)
        state = db.get(SyncState, "documents")
        assert missing is not None
        assert missing.deleted_at is not None
        assert missing.deleted_at.startswith("DELETED in Paperless")
        assert synced is not None
        assert synced.title == "Remote Synced Doc"
        assert state is not None
        assert state.status == "idle"
        assert state.processed == 1
        assert state.total == 1
        assert state.last_synced_at is not None


def test_sync_documents_insert_only_skips_existing_rows(api_client: Any, monkeypatch: Any) -> None:
    import app.routes.sync as sync_routes

    _insert_local_document(1101, "Existing Local Doc")
    monkeypatch.setenv("QUEUE_ENABLED", "0")

    monkeypatch.setattr(
        sync_routes.paperless,
        "list_documents",
        lambda _settings, page, page_size, modified__gte=None: {
            "count": 2,
            "next": None,
            "results": [
                {
                    "id": 1101,
                    "title": "Remote Existing Title",
                    "content": "existing content",
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
                {
                    "id": 1102,
                    "title": "Brand New Doc",
                    "content": "new content",
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
            ],
        },
    )

    response = api_client.post(
        "/sync/documents",
        params={"incremental": False, "insert_only": True, "embed": False},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 2
    assert payload["upserted"] == 1
    assert payload["embedded"] == 0

    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        existing = db.get(Document, 1101)
        inserted = db.get(Document, 1102)
        assert existing is not None
        assert existing.title == "Existing Local Doc"
        assert inserted is not None
        assert inserted.title == "Brand New Doc"
