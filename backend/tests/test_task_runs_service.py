from __future__ import annotations

import pytest
from sqlalchemy import text

from app.models import TaskRun
from app.services.task_runs import create_task_run, find_latest_checkpoint, finish_task_run, list_task_runs


def test_find_latest_checkpoint_returns_newest_dict(session_factory):
    with session_factory() as db:
        db.add(
            TaskRun(
                doc_id=1756,
                task="vision_ocr",
                source="vision_ocr",
                status="failed",
                worker_id="worker:test",
                attempt=1,
                checkpoint_json='{"stage":"vision_ocr","current":10,"total":37}',
                started_at="2026-02-12T10:00:00+00:00",
                finished_at="2026-02-12T10:00:02+00:00",
                created_at="2026-02-12T10:00:00+00:00",
                updated_at="2026-02-12T10:00:02+00:00",
            )
        )
        db.add(
            TaskRun(
                doc_id=1756,
                task="vision_ocr",
                source="vision_ocr",
                status="failed",
                worker_id="worker:test",
                attempt=2,
                checkpoint_json='{"stage":"vision_ocr","current":20,"total":37}',
                started_at="2026-02-12T10:01:00+00:00",
                finished_at="2026-02-12T10:01:02+00:00",
                created_at="2026-02-12T10:01:00+00:00",
                updated_at="2026-02-12T10:01:02+00:00",
            )
        )
        db.commit()

    with session_factory() as db:
        checkpoint = find_latest_checkpoint(
            db,
            doc_id=1756,
            task="vision_ocr",
            source="vision_ocr",
        )

    assert checkpoint is not None
    assert checkpoint["stage"] == "vision_ocr"
    assert checkpoint["current"] == 20
    assert checkpoint["total"] == 37


def test_find_latest_checkpoint_returns_none_for_invalid_payload(session_factory):
    with session_factory() as db:
        db.add(
            TaskRun(
                doc_id=2000,
                task="embeddings_vision",
                source="vision_ocr",
                status="failed",
                worker_id="worker:test",
                attempt=1,
                checkpoint_json="not-json",
                started_at="2026-02-12T11:00:00+00:00",
                finished_at="2026-02-12T11:00:02+00:00",
                created_at="2026-02-12T11:00:00+00:00",
                updated_at="2026-02-12T11:00:02+00:00",
            )
        )
        db.commit()

    with session_factory() as db:
        checkpoint = find_latest_checkpoint(
            db,
            doc_id=2000,
            task="embeddings_vision",
            source="vision_ocr",
        )

    assert checkpoint is None


def _insert_duplicate_task_run(db, *, row_id: int, doc_id: int, task: str, source: str | None) -> None:
    db.execute(
        text(
            """
            INSERT INTO task_runs
              (id, doc_id, task, source, status, worker_id, attempt, started_at, finished_at, created_at, updated_at)
            VALUES
              (:id, :doc_id, :task, :source, :status, :worker_id, :attempt, :started_at, :finished_at, :created_at, :updated_at)
            """
        ),
        {
            "id": row_id,
            "doc_id": doc_id,
            "task": task,
            "source": source,
            "status": "failed",
            "worker_id": "worker:test",
            "attempt": 1,
            "started_at": "2026-02-12T11:01:00+00:00",
            "finished_at": "2026-02-12T11:01:10+00:00",
            "created_at": "2026-02-12T11:01:00+00:00",
            "updated_at": "2026-02-12T11:01:10+00:00",
        },
    )


def test_finish_task_run_recovers_from_pending_rollback(session_factory):
    with session_factory() as db:
        row = create_task_run(
            db,
            doc_id=3001,
            task="sync",
            source=None,
            payload={"doc_id": 3001, "task": "sync"},
            worker_id="worker:test",
            attempt=1,
        )
        row_id = int(row.id)
        with pytest.raises(Exception):
            _insert_duplicate_task_run(db, row_id=row_id, doc_id=3001, task="sync", source=None)
            db.commit()

        finish_task_run(db, run_id=row_id, status="done", duration_ms=42)
        refreshed = db.get(TaskRun, row_id)
        assert refreshed is not None
        assert refreshed.status == "done"
        assert refreshed.duration_ms == 42


def test_list_task_runs_recovers_from_pending_rollback(session_factory):
    with session_factory() as db:
        row = create_task_run(
            db,
            doc_id=3002,
            task="sync",
            source=None,
            payload={"doc_id": 3002, "task": "sync"},
            worker_id="worker:test",
            attempt=1,
        )
        row_id = int(row.id)
        with pytest.raises(Exception):
            _insert_duplicate_task_run(db, row_id=row_id, doc_id=3002, task="sync", source=None)
            db.commit()

        total, rows = list_task_runs(db, doc_id=3002, limit=10)
        assert total >= 1
        assert any(item.id == row_id for item in rows)
