from __future__ import annotations

import os
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import load_settings
from app.models import Document
from app.services.documents.sync_operations import run_documents_sync


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


def _insert_local_document(session_factory: Any, doc_id: int, title: str) -> None:
    with session_factory() as db:
        db.add(
            Document(
                id=doc_id,
                title=title,
                created="2026-03-11T10:00:00+00:00",
                modified="2026-03-11T10:00:00+00:00",
            )
        )
        db.commit()


def test_run_documents_sync_page_only_mark_missing_skips_missing_pass(session_factory: Any) -> None:
    settings = load_settings()
    _insert_local_document(session_factory, 5001, "Unseen Local Doc")

    def _list_documents(
        _settings: Any, page: int, page_size: int, modified__gte: str | None = None
    ) -> dict[str, Any]:
        assert page == 1
        return _page_payload(1, None, [_doc_payload(5002, "Remote Synced Doc", "remote content")])

    db = session_factory()
    try:
        result = run_documents_sync(
            db=db,
            settings=settings,
            page_size=50,
            incremental=False,
            embed=False,
            page=1,
            page_only=True,
            force_embed=False,
            mark_missing=True,
            insert_only=False,
            list_documents_fn=_list_documents,
            build_task_sequence_fn=lambda *args, **kwargs: [],
            enqueue_task_sequence_fn=lambda *args, **kwargs: None,
        )
    finally:
        db.close()

    assert result["marked_deleted"] is None

    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as verify_db:
        doc = verify_db.get(Document, 5001)
        assert doc is not None
        assert doc.deleted_at is None


def test_run_documents_sync_page_gt_1_mark_missing_skips_missing_pass(session_factory: Any) -> None:
    settings = load_settings()
    _insert_local_document(session_factory, 5101, "Unseen Local Doc")

    def _list_documents(
        _settings: Any, page: int, page_size: int, modified__gte: str | None = None
    ) -> dict[str, Any]:
        if page != 2:
            raise AssertionError("unexpected page requested")
        return _page_payload(1, None, [_doc_payload(5102, "Remote Page Two Doc", "remote content")])

    db = session_factory()
    try:
        result = run_documents_sync(
            db=db,
            settings=settings,
            page_size=50,
            incremental=False,
            embed=False,
            page=2,
            page_only=False,
            force_embed=False,
            mark_missing=True,
            insert_only=False,
            list_documents_fn=_list_documents,
            build_task_sequence_fn=lambda *args, **kwargs: [],
            enqueue_task_sequence_fn=lambda *args, **kwargs: None,
        )
    finally:
        db.close()

    assert result["marked_deleted"] is None
    assert result["upserted"] == 1

    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as verify_db:
        doc = verify_db.get(Document, 5101)
        assert doc is not None
        assert doc.deleted_at is None


def test_run_documents_sync_full_walk_mark_missing_still_marks(session_factory: Any) -> None:
    settings = load_settings()
    _insert_local_document(session_factory, 5201, "Unseen Local Doc")

    def _list_documents(
        _settings: Any, page: int, page_size: int, modified__gte: str | None = None
    ) -> dict[str, Any]:
        assert page == 1
        return _page_payload(1, None, [_doc_payload(5202, "Remote Synced Doc", "remote content")])

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
            mark_missing=True,
            insert_only=False,
            list_documents_fn=_list_documents,
            build_task_sequence_fn=lambda *args, **kwargs: [],
            enqueue_task_sequence_fn=lambda *args, **kwargs: None,
        )
    finally:
        db.close()

    assert result["marked_deleted"] == 1

    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as verify_db:
        doc = verify_db.get(Document, 5201)
        assert doc is not None
        assert doc.deleted_at is not None
        assert doc.deleted_at.startswith("DELETED in Paperless")


def test_run_documents_sync_empty_remote_list_mark_missing_does_not_mass_delete(
    session_factory: Any,
) -> None:
    """An empty remote walk must not mark every local document deleted.

    Regression for BT-007: with ``mark_missing`` and a remote list that returns
    no documents, ``seen_ids`` stays empty and ``~Document.id.in_([])`` would
    otherwise match the entire local library. The guard skips the mark-missing
    pass so the local documents keep their state.
    """
    settings = load_settings()
    _insert_local_document(session_factory, 5301, "Local Doc A")
    _insert_local_document(session_factory, 5302, "Local Doc B")

    def _list_documents(
        _settings: Any, page: int, page_size: int, modified__gte: str | None = None
    ) -> dict[str, Any]:
        assert page == 1
        return _page_payload(0, None, [])

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
            mark_missing=True,
            insert_only=False,
            list_documents_fn=_list_documents,
            build_task_sequence_fn=lambda *args, **kwargs: [],
            enqueue_task_sequence_fn=lambda *args, **kwargs: None,
        )
    finally:
        db.close()

    # The mark-missing pass is skipped, so nothing is marked deleted.
    assert result["marked_deleted"] == 0

    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as verify_db:
        for doc_id in (5301, 5302):
            doc = verify_db.get(Document, doc_id)
            assert doc is not None
            assert doc.deleted_at is None


def test_run_documents_sync_reduced_remote_list_mark_missing_marks_only_missing(
    session_factory: Any,
) -> None:
    """A non-empty reduced remote list marks only the unseen local document."""
    settings = load_settings()
    _insert_local_document(session_factory, 5401, "Unseen Local Doc")
    _insert_local_document(session_factory, 5402, "Seen Local Doc")

    def _list_documents(
        _settings: Any, page: int, page_size: int, modified__gte: str | None = None
    ) -> dict[str, Any]:
        assert page == 1
        return _page_payload(1, None, [_doc_payload(5402, "Seen Remote Doc", "remote content")])

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
            mark_missing=True,
            insert_only=False,
            list_documents_fn=_list_documents,
            build_task_sequence_fn=lambda *args, **kwargs: [],
            enqueue_task_sequence_fn=lambda *args, **kwargs: None,
        )
    finally:
        db.close()

    assert result["marked_deleted"] == 1

    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as verify_db:
        missing = verify_db.get(Document, 5401)
        seen = verify_db.get(Document, 5402)
        assert missing is not None
        assert missing.deleted_at is not None
        assert missing.deleted_at.startswith("DELETED in Paperless")
        assert seen is not None
        assert seen.deleted_at is None
