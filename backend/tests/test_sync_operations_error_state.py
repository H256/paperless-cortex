from __future__ import annotations

import os
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import load_settings
from app.models import Document, SyncState
from app.services.documents.sync_operations import embed_documents, run_documents_sync


def _doc_payload(doc_id: int, title: str, content: str) -> dict[str, Any]:
    return {
        "id": doc_id,
        "title": title,
        "content": content,
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


def _page_payload(count: int, next_value: str | None, docs: list[dict[str, Any]]) -> dict[str, Any]:
    return {"count": count, "next": next_value, "results": docs}


def test_run_documents_sync_marks_error_state_on_mid_sync_failure(session_factory: Any) -> None:
    settings = load_settings()

    def _list_documents(
        _settings: Any, page: int, page_size: int, modified__gte: str | None = None
    ) -> dict[str, Any]:
        if page == 1:
            return _page_payload(2, "2", [_doc_payload(2001, "Page One Doc", "page one content")])
        raise RuntimeError("paperless 5xx")

    db = session_factory()
    try:
        with pytest.raises(RuntimeError, match="paperless 5xx"):
            run_documents_sync(
                db=db,
                settings=settings,
                page_size=50,
                incremental=False,
                embed=False,
                page=1,
                page_only=False,
                force_embed=False,
                mark_missing=False,
                insert_only=False,
                list_documents_fn=_list_documents,
                build_task_sequence_fn=lambda *args, **kwargs: [],
                enqueue_task_sequence_fn=lambda *args, **kwargs: None,
            )
    finally:
        db.close()

    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as verify_db:
        state = verify_db.get(SyncState, "documents")
        assert state is not None
        assert state.status == "error"
        # Per-page commits persist before the failure, so page-1 work survives.
        doc = verify_db.get(Document, 2001)
        assert doc is not None
        assert doc.title == "Page One Doc"


def test_embed_documents_marks_error_state_on_embedding_failure(
    session_factory: Any, monkeypatch: Any
) -> None:
    import app.services.documents.sync_operations as sync_operations

    monkeypatch.setenv("EMBEDDING_MODEL", "test-model")
    settings = load_settings()

    monkeypatch.setattr(
        sync_operations, "ensure_embedding_collection", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        sync_operations, "collect_page_texts", lambda *_args, **_kwargs: (None, [], [])
    )
    monkeypatch.setattr(sync_operations, "delete_points_for_doc", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(sync_operations, "upsert_points", lambda *_args, **_kwargs: None)

    def _embed_text(_settings: Any, _text: str) -> list[float]:
        raise RuntimeError("embedding boom")

    monkeypatch.setattr(sync_operations, "embed_text", _embed_text)

    with session_factory() as db:
        doc = Document(id=901, title="Doc", content="some content to embed")
        db.add(doc)
        db.commit()
        db.refresh(doc)

        with pytest.raises(RuntimeError, match="embedding boom"):
            embed_documents(db, settings, [doc])

    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as verify_db:
        state = verify_db.get(SyncState, "embeddings")
        assert state is not None
        assert state.status == "error"


def test_sync_documents_route_mid_sync_failure_marks_error_state(
    api_client: Any, monkeypatch: Any
) -> None:
    import app.routes.sync as sync_routes

    monkeypatch.setenv("QUEUE_ENABLED", "0")

    def _list_documents(
        _settings: Any, page: int, page_size: int, modified__gte: str | None = None
    ) -> dict[str, Any]:
        if page == 1:
            return _page_payload(2, "2", [_doc_payload(3001, "Remote Synced Doc", "remote content")])
        raise RuntimeError("paperless 5xx")

    monkeypatch.setattr(sync_routes.paperless, "list_documents", _list_documents)

    with pytest.raises(RuntimeError):
        api_client.post("/sync/documents", params={"incremental": False, "embed": False})

    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        state = db.get(SyncState, "documents")
        assert state is not None
        assert state.status == "error"


def test_run_documents_sync_success_sets_idle_state(session_factory: Any) -> None:
    settings = load_settings()

    def _list_documents(
        _settings: Any, page: int, page_size: int, modified__gte: str | None = None
    ) -> dict[str, Any]:
        if page == 1:
            return _page_payload(1, None, [_doc_payload(4001, "Single Page Doc", "single page content")])
        raise AssertionError("unexpected page requested")

    db = session_factory()
    try:
        result = run_documents_sync(
            db=db,
            settings=settings,
            page_size=50,
            incremental=False,
            embed=False,
            page=1,
            page_only=False,
            force_embed=False,
            mark_missing=False,
            insert_only=False,
            list_documents_fn=_list_documents,
            build_task_sequence_fn=lambda *args, **kwargs: [],
            enqueue_task_sequence_fn=lambda *args, **kwargs: None,
        )
    finally:
        db.close()

    assert result["count"] == 1
    assert result["upserted"] == 1
    assert result["embedded"] == 0

    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as verify_db:
        state = verify_db.get(SyncState, "documents")
        assert state is not None
        assert state.status == "idle"
        assert state.last_synced_at is not None
