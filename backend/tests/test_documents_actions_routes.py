from __future__ import annotations

import os
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Document


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


def test_cleanup_texts_enqueue_builds_tasks(api_client: Any, monkeypatch: Any) -> None:
    from app.routes import documents_actions

    monkeypatch.setenv("QUEUE_ENABLED", "1")
    monkeypatch.setattr(documents_actions, "require_queue_enabled", lambda _settings: True)

    captured: list[dict[str, object]] = []

    def _enqueue_task_sequence(_settings: Any, tasks: list[dict[str, object]]) -> int:
        captured.extend(tasks)
        return len(tasks)

    monkeypatch.setattr(documents_actions, "enqueue_task_sequence", _enqueue_task_sequence)

    response = api_client.post(
        "/documents/cleanup-texts",
        json={
            "doc_ids": [11, 12],
            "source": "vision_ocr",
            "clear_first": True,
            "enqueue": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["queued"] is True
    assert payload["docs"] == 2
    assert payload["enqueued"] == 2
    assert captured == [
        {"doc_id": 11, "task": "cleanup_texts", "clear_first": True, "source": "vision_ocr"},
        {"doc_id": 12, "task": "cleanup_texts", "clear_first": True, "source": "vision_ocr"},
    ]


def test_reset_and_reprocess_enqueues_priority_tasks(api_client: Any, monkeypatch: Any) -> None:
    from app.routes import documents_actions
    from app.services.integrations import paperless

    _insert_local_document(144, "Reset Queue Doc")
    monkeypatch.setenv("QUEUE_ENABLED", "1")
    monkeypatch.setattr(documents_actions, "require_queue_enabled", lambda _settings: True)
    monkeypatch.setattr(documents_actions, "delete_points_for_doc", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda _settings, doc_id: {
            "id": doc_id,
            "title": "Reset Queue Doc",
            "content": "queued content",
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
        documents_actions,
        "build_task_sequence",
        lambda _settings, doc_id, include_sync, force: [
            {"doc_id": doc_id, "task": "vision_ocr"},
            {"doc_id": doc_id, "task": "embeddings_vision"},
        ],
    )

    queued: list[dict[str, object]] = []

    def _enqueue_front(_settings: Any, tasks: list[dict[str, object]], *, force: bool = False) -> int:
        queued.extend(tasks)
        assert force is True
        return len(tasks)

    monkeypatch.setattr(documents_actions, "enqueue_task_sequence_front", _enqueue_front)

    response = api_client.post("/documents/144/operations/reset-and-reprocess")
    assert response.status_code == 200
    payload = response.json()
    assert payload["doc_id"] == 144
    assert payload["synced"] is True
    assert payload["reset"] is True
    assert payload["enqueued"] == 2
    assert queued == [
        {"doc_id": 144, "task": "vision_ocr"},
        {"doc_id": 144, "task": "embeddings_vision"},
    ]


def test_missing_vector_chunk_audit_route_returns_typed_payload(
    api_client: Any,
    monkeypatch: Any,
) -> None:
    from app.routes import documents_actions

    monkeypatch.setattr(
        documents_actions,
        "audit_missing_vector_chunks",
        lambda _settings, _db, limit=100: {
            "provider": "weaviate",
            "scanned_docs": 2,
            "affected_docs": 1,
            "fully_missing_docs": 1,
            "partial_missing_docs": 0,
            "limit": limit,
            "truncated": False,
            "items": [
                {
                    "doc_id": 67,
                    "title": "Missing Vision Doc",
                    "embedding_source": "vision",
                    "chunk_count": 4,
                    "expected_vectors": 4,
                    "found_vectors": 0,
                    "fully_missing": True,
                    "embedded_at": "2026-03-14T09:51:13.631637+00:00",
                }
            ],
        },
    )

    response = api_client.get("/documents/audit/missing-vector-chunks?limit=25")
    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "weaviate"
    assert payload["scanned_docs"] == 2
    assert payload["affected_docs"] == 1
    assert payload["limit"] == 25
    assert payload["items"][0]["doc_id"] == 67
