from __future__ import annotations

import os
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import load_settings
from app.models import SyncState
from app.services.documents.sync_operations import run_documents_sync
from app.services.pipeline.sync_state import claim_documents_sync


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


def _insert_sync_state(
    key: str,
    *,
    status: str,
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


def _run_sync(db: Session, settings: Any, list_documents_fn: Any) -> dict[str, Any]:
    return run_documents_sync(
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
        list_documents_fn=list_documents_fn,
        build_task_sequence_fn=lambda *args, **kwargs: [],
        enqueue_task_sequence_fn=lambda *args, **kwargs: None,
    )


def test_claim_documents_sync_wins_on_clean_state(session_factory: Any) -> None:
    db = session_factory()
    try:
        assert claim_documents_sync(db) is True
    finally:
        db.close()

    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as verify_db:
        state = verify_db.get(SyncState, "documents")
        assert state is not None
        assert state.status == "running"
        assert state.cancel_requested is False
        assert state.started_at is not None


def test_claim_documents_sync_loses_when_already_running(session_factory: Any) -> None:
    _insert_sync_state("documents", status="running", processed=1, total=4)

    db = session_factory()
    try:
        assert claim_documents_sync(db) is False
    finally:
        db.close()

    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as verify_db:
        state = verify_db.get(SyncState, "documents")
        assert state is not None
        # The in-flight state is untouched by the losing claim.
        assert state.status == "running"
        assert state.processed == 1
        assert state.total == 4


def test_run_documents_sync_skips_when_already_running(session_factory: Any) -> None:
    settings = load_settings()
    _insert_sync_state("documents", status="running", processed=2, total=9)

    def _list_documents(
        _settings: Any, page: int, page_size: int, modified__gte: str | None = None
    ) -> dict[str, Any]:
        return _page_payload(1, None, [_doc_payload(5001, "Should Not Run", "content")])

    db = session_factory()
    try:
        result = _run_sync(db, settings, _list_documents)
    finally:
        db.close()

    assert result["status"] == "running"
    assert result["count"] == 0
    assert result["upserted"] == 0

    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as verify_db:
        state = verify_db.get(SyncState, "documents")
        assert state is not None
        # The in-flight run's progress/total are preserved (no last-writer-wins).
        assert state.status == "running"
        assert state.processed == 2
        assert state.total == 9


def test_claim_documents_sync_reopens_after_completion(session_factory: Any) -> None:
    settings = load_settings()

    def _list_documents(
        _settings: Any, page: int, page_size: int, modified__gte: str | None = None
    ) -> dict[str, Any]:
        return _page_payload(1, None, [_doc_payload(6001, "Single Page Doc", "single page content")])

    db = session_factory()
    try:
        # First run claims and completes, leaving status='idle'.
        first = _run_sync(db, settings, _list_documents)
        assert first.get("status") != "running"
        assert first["upserted"] == 1
    finally:
        db.close()

    # A subsequent claim succeeds again because the state is no longer 'running'.
    db2 = session_factory()
    try:
        assert claim_documents_sync(db2) is True
    finally:
        db2.close()
