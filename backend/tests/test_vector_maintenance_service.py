"""Payload-level tests for vector maintenance deletion (issue #162).

The vector-store deletion must be authoritative: when it fails, no DB rows
(DocumentEmbedding / TaskRun) may be deleted or committed. The payload
functions accept injectable vector-delete stubs, which record call order so
the tests can prove the DB wipe happens only after the vector delete call.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
import pytest

from app.config import load_settings
from app.models import Document, DocumentEmbedding, TaskRun
from app.services.search.vector_maintenance import (
    delete_embeddings_payload,
    delete_similarity_index_payload,
)

logger = logging.getLogger("test.vector_maintenance")

VECTOR_ERROR_TYPES = [httpx.HTTPError, RuntimeError, ValueError]


def _seed_document(session_factory: Any, doc_id: int, title: str) -> None:
    with session_factory() as db:
        db.add(
            Document(
                id=doc_id,
                title=title,
                created="2026-02-10T10:00:00+00:00",
                modified="2026-02-10T10:00:00+00:00",
            )
        )
        db.commit()


def _seed_embedding_row(session_factory: Any, doc_id: int, chunk_count: int = 2) -> None:
    with session_factory() as db:
        db.add(DocumentEmbedding(doc_id=doc_id, embedding_source="paperless", chunk_count=chunk_count))
        db.commit()


def _seed_task_run(session_factory: Any, *, doc_id: int, task: str) -> None:
    with session_factory() as db:
        db.add(
            TaskRun(
                doc_id=doc_id,
                task=task,
                source=None,
                status="completed",
                worker_id="worker:test",
                attempt=1,
                started_at="2026-02-20T09:16:44+00:00",
                finished_at="2026-02-20T09:17:16+00:00",
                created_at="2026-02-20T09:16:44+00:00",
                updated_at="2026-02-20T09:17:16+00:00",
            )
        )
        db.commit()


def _embedding_row_count(session_factory: Any) -> int:
    with session_factory() as db:
        return db.query(DocumentEmbedding).count()


def _task_run_count(session_factory: Any, doc_id: int, task: str) -> int:
    with session_factory() as db:
        return db.query(TaskRun).filter(TaskRun.doc_id == doc_id, TaskRun.task == task).count()


@pytest.mark.parametrize("error_type", VECTOR_ERROR_TYPES)
def test_delete_embeddings_doc_vector_failure_keeps_db_row(session_factory: Any, error_type: Any) -> None:
    settings = load_settings()
    _seed_document(session_factory, 48, "Doc 48")
    _seed_embedding_row(session_factory, 48)

    def raise_vector_error(_settings: Any, _doc_id: int) -> None:
        raise error_type("vector store unavailable")

    with session_factory() as db:
        result = delete_embeddings_payload(
            settings,
            db,
            doc_id=48,
            logger=logger,
            delete_points_for_doc_fn=raise_vector_error,
        )

    assert result == {"deleted": 0, "qdrant_deleted": 0, "qdrant_errors": 1}
    with session_factory() as db:
        assert db.get(DocumentEmbedding, 48) is not None


def test_delete_embeddings_doc_success_deletes_after_vector_delete(session_factory: Any) -> None:
    settings = load_settings()
    _seed_document(session_factory, 48, "Doc 48")
    _seed_embedding_row(session_factory, 48)

    calls: list[tuple[Any, int]] = []
    row_present_at_vector_delete: list[bool] = []

    def recording_delete(st_settings: Any, st_doc_id: int) -> None:
        calls.append((st_settings, st_doc_id))
        with session_factory() as check_db:
            row_present_at_vector_delete.append(check_db.get(DocumentEmbedding, 48) is not None)

    with session_factory() as db:
        result = delete_embeddings_payload(
            settings,
            db,
            doc_id=48,
            logger=logger,
            delete_points_for_doc_fn=recording_delete,
        )

    assert result == {"deleted": 1, "qdrant_deleted": 1, "qdrant_errors": 0}
    assert len(calls) == 1
    assert calls[0] == (settings, 48)
    # Ordering: the DB row must still exist when the vector delete runs.
    assert row_present_at_vector_delete == [True]
    with session_factory() as db:
        assert db.get(DocumentEmbedding, 48) is None


def test_delete_embeddings_all_vector_failure_keeps_db_rows(session_factory: Any) -> None:
    settings = load_settings()
    _seed_document(session_factory, 50, "Doc 50")
    _seed_document(session_factory, 51, "Doc 51")
    _seed_embedding_row(session_factory, 50)
    _seed_embedding_row(session_factory, 51)

    def raise_vector_error(_settings: Any) -> None:
        raise RuntimeError("vector store unavailable")

    with session_factory() as db:
        result = delete_embeddings_payload(
            settings,
            db,
            doc_id=None,
            logger=logger,
            delete_all_chunk_points_fn=raise_vector_error,
        )

    assert result == {"deleted": 0, "qdrant_deleted": 0, "qdrant_errors": 1}
    with session_factory() as db:
        assert db.get(DocumentEmbedding, 50) is not None
        assert db.get(DocumentEmbedding, 51) is not None


def test_delete_embeddings_all_success_wipes_after_vector_delete(session_factory: Any) -> None:
    settings = load_settings()
    _seed_document(session_factory, 50, "Doc 50")
    _seed_document(session_factory, 51, "Doc 51")
    _seed_embedding_row(session_factory, 50)
    _seed_embedding_row(session_factory, 51)

    calls: list[str] = []
    row_count_at_vector_delete: list[int] = []

    def recording_delete_all(_settings: Any) -> None:
        calls.append("delete_all")
        with session_factory() as check_db:
            row_count_at_vector_delete.append(check_db.query(DocumentEmbedding).count())

    with session_factory() as db:
        result = delete_embeddings_payload(
            settings,
            db,
            doc_id=None,
            logger=logger,
            delete_all_chunk_points_fn=recording_delete_all,
        )

    assert result == {"deleted": 1, "qdrant_deleted": 1, "qdrant_errors": 0}
    assert calls == ["delete_all"]
    # Ordering: both DB rows must still exist when the vector delete runs.
    assert row_count_at_vector_delete == [2]
    assert _embedding_row_count(session_factory) == 0


def test_delete_similarity_index_vector_failure_keeps_task_runs(session_factory: Any) -> None:
    settings = load_settings()
    _seed_document(session_factory, 77, "Doc 77")
    _seed_task_run(session_factory, doc_id=77, task="similarity_index")
    _seed_task_run(session_factory, doc_id=77, task="embeddings_vision")

    def raise_vector_error(_settings: Any, *, doc_id: int | None = None) -> None:
        raise RuntimeError("vector store unavailable")

    for doc_id in (None, 77):
        with session_factory() as db:
            result = delete_similarity_index_payload(
                settings,
                db,
                doc_id=doc_id,
                logger=logger,
                delete_similarity_points_fn=raise_vector_error,
            )
        assert result == {"deleted": 0, "qdrant_deleted": 0, "qdrant_errors": 1}

    assert _task_run_count(session_factory, 77, "similarity_index") == 1
    assert _task_run_count(session_factory, 77, "embeddings_vision") == 1


def test_delete_similarity_index_success_deletes_after_vector_delete(session_factory: Any) -> None:
    settings = load_settings()
    _seed_document(session_factory, 77, "Doc 77")
    _seed_document(session_factory, 78, "Doc 78")
    _seed_task_run(session_factory, doc_id=77, task="similarity_index")
    _seed_task_run(session_factory, doc_id=78, task="similarity_index")
    _seed_task_run(session_factory, doc_id=77, task="embeddings_vision")

    calls: list[int | None] = []
    similarity_count_at_vector_delete: list[int] = []

    def recording_delete(_settings: Any, *, doc_id: int | None = None) -> None:
        calls.append(doc_id)
        with session_factory() as check_db:
            similarity_count_at_vector_delete.append(
                check_db.query(TaskRun).filter(TaskRun.task == "similarity_index").count()
            )

    # Selective delete for doc 77: ordering check plus targeted removal.
    with session_factory() as db:
        result = delete_similarity_index_payload(
            settings,
            db,
            doc_id=77,
            logger=logger,
            delete_similarity_points_fn=recording_delete,
        )

    assert result == {"deleted": 1, "qdrant_deleted": 1, "qdrant_errors": 0}
    assert calls == [77]
    # Ordering: both similarity rows must still exist when the vector delete runs.
    assert similarity_count_at_vector_delete == [2]
    assert _task_run_count(session_factory, 77, "similarity_index") == 0
    assert _task_run_count(session_factory, 78, "similarity_index") == 1
    assert _task_run_count(session_factory, 77, "embeddings_vision") == 1

    # Delete-all removes the remaining row; the control row stays.
    with session_factory() as db:
        result = delete_similarity_index_payload(
            settings,
            db,
            doc_id=None,
            logger=logger,
            delete_similarity_points_fn=recording_delete,
        )

    assert result == {"deleted": 1, "qdrant_deleted": 1, "qdrant_errors": 0}
    assert calls == [77, None]
    assert similarity_count_at_vector_delete == [2, 1]
    assert _task_run_count(session_factory, 77, "similarity_index") == 0
    assert _task_run_count(session_factory, 78, "similarity_index") == 0
    assert _task_run_count(session_factory, 77, "embeddings_vision") == 1


def test_delete_embeddings_doc_missing_row_vector_failure(session_factory: Any) -> None:
    settings = load_settings()
    _seed_document(session_factory, 48, "Doc 48")

    def raise_vector_error(_settings: Any, _doc_id: int) -> None:
        raise RuntimeError("vector store unavailable")

    with session_factory() as db:
        result = delete_embeddings_payload(
            settings,
            db,
            doc_id=48,
            logger=logger,
            delete_points_for_doc_fn=raise_vector_error,
        )

    assert result == {"deleted": 0, "qdrant_deleted": 0, "qdrant_errors": 1}
    with session_factory() as db:
        assert db.get(DocumentEmbedding, 48) is None
