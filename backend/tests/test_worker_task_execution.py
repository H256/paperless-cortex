from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.exc import OperationalError

from app.config import load_settings
from app.exceptions import WorkerError
from app.models import TaskRun
from app.services.pipeline import worker_task_execution
from app.services.pipeline.worker_task_execution import execute_worker_task
from app.services.runtime.metrics import snapshot_metrics


def test_execute_worker_task_requeues_retryable_failure(
    session_factory: Any, monkeypatch: Any
) -> None:
    monkeypatch.setenv("WORKER_MAX_RETRIES", "2")
    settings = load_settings()

    with session_factory() as db:
        result = execute_worker_task(
            settings=settings,
            db=db,
            worker_token="worker:test",
            doc_id=91,
            task_type="sync",
            task={"doc_id": 91, "task": "sync"},
            retry_attempt=0,
            dispatch_worker_task_fn=lambda **_kwargs: (_ for _ in ()).throw(
                WorkerError(
                    "timed out",
                    task="sync",
                    attempt=1,
                    original_exception=RuntimeError("timed out"),
                )
            ),
            build_handler_fn=lambda *_args: None,
            process_vision_ocr_force_fn=lambda *_args, **_kwargs: None,
            process_full_doc_fn=lambda *_args, **_kwargs: None,
            set_task_checkpoint_fn=lambda *_args, **_kwargs: None,
            logger=logging.getLogger(__name__),
        )

        assert result["pending_retry_payload"] == {"doc_id": 91, "task": "sync", "retry_count": 1}
        assert result["pending_retry_delay_seconds"] == 5
        assert result["pending_dead_letter"] is None

        row = db.query(TaskRun).filter(TaskRun.doc_id == 91, TaskRun.task == "sync").one()
        assert row.status == "retrying"
        assert row.error_type == "LLM_TIMEOUT"
        assert row.error_message == "timed out"
        metrics = snapshot_metrics()
        assert any(
            item["name"] == "worker_task_retries_total"
            and item["labels"].get("task") == "sync"
            and item["labels"].get("error_type") == "LLM_TIMEOUT"
            for item in metrics["counters"]
        )
        assert any(
            item["name"] == "worker_task_duration_ms"
            and item["labels"].get("task") == "sync"
            and item["labels"].get("outcome") == "retrying"
            for item in metrics["timers"]
        )


def test_execute_worker_task_dead_letters_non_retryable_vector_failure(
    session_factory: Any, monkeypatch: Any
) -> None:
    monkeypatch.setenv("WORKER_MAX_RETRIES", "2")
    settings = load_settings()

    with session_factory() as db:
        result = execute_worker_task(
            settings=settings,
            db=db,
            worker_token="worker:test",
            doc_id=92,
            task_type="similarity_index",
            task={"doc_id": 92, "task": "similarity_index"},
            retry_attempt=0,
            dispatch_worker_task_fn=lambda **_kwargs: (_ for _ in ()).throw(
                RuntimeError("chunk vectors missing in active vector store")
            ),
            build_handler_fn=lambda *_args: None,
            process_vision_ocr_force_fn=lambda *_args, **_kwargs: None,
            process_full_doc_fn=lambda *_args, **_kwargs: None,
            set_task_checkpoint_fn=lambda *_args, **_kwargs: None,
            logger=logging.getLogger(__name__),
        )

        assert result["pending_retry_payload"] is None
        assert result["pending_retry_delay_seconds"] is None
        assert result["pending_dead_letter"] == {
            "task": {"doc_id": 92, "task": "similarity_index"},
            "error_type": "VECTOR_CHUNKS_MISSING",
            "error_message": "chunk vectors missing in active vector store",
            "attempt": 1,
        }

        row = db.query(TaskRun).filter(TaskRun.doc_id == 92, TaskRun.task == "similarity_index").one()
        assert row.status == "failed"
        assert row.error_type == "VECTOR_CHUNKS_MISSING"
        assert row.error_message == "chunk vectors missing in active vector store"
        metrics = snapshot_metrics()
        assert any(
            item["name"] == "worker_task_dead_letters_total"
            and item["labels"].get("task") == "similarity_index"
            and item["labels"].get("error_type") == "VECTOR_CHUNKS_MISSING"
            for item in metrics["counters"]
        )
        assert any(
            item["name"] == "worker_task_duration_ms"
            and item["labels"].get("task") == "similarity_index"
            and item["labels"].get("outcome") == "failed"
            for item in metrics["timers"]
        )


def test_execute_worker_task_requeues_when_create_task_run_fails(
    session_factory: Any, monkeypatch: Any
) -> None:
    """PL-002: a transient DB failure in create_task_run must re-enqueue the
    popped task delayed (while retries remain), not immediately dead-letter it."""
    monkeypatch.setenv("WORKER_MAX_RETRIES", "2")
    settings = load_settings()

    def _raise_create_task_run(*_args: Any, **_kwargs: Any) -> Any:
        raise OperationalError(
            "INSERT INTO task_runs ...",
            {},
            RuntimeError("task_runs insert failed"),
        )

    monkeypatch.setattr(worker_task_execution, "create_task_run", _raise_create_task_run)

    with session_factory() as db:
        result = execute_worker_task(
            settings=settings,
            db=db,
            worker_token="worker:test",
            doc_id=93,
            task_type="sync",
            task={"doc_id": 93, "task": "sync"},
            retry_attempt=0,
            dispatch_worker_task_fn=lambda **_kwargs: None,
            build_handler_fn=lambda *_args: None,
            process_vision_ocr_force_fn=lambda *_args, **_kwargs: None,
            process_full_doc_fn=lambda *_args, **_kwargs: None,
            set_task_checkpoint_fn=lambda *_args, **_kwargs: None,
            logger=logging.getLogger(__name__),
        )

        # The popped task must be re-enqueued delayed, not dead-lettered.
        assert result["pending_retry_payload"] == {
            "doc_id": 93,
            "task": "sync",
            "retry_count": 1,
        }
        assert result["pending_retry_delay_seconds"] == 5
        assert result["pending_dead_letter"] is None

        # No TaskRun row was created (the write failed before commit).
        rows = db.query(TaskRun).filter(TaskRun.doc_id == 93).all()
        assert rows == []

        metrics = snapshot_metrics()
        assert any(
            item["name"] == "worker_task_retries_total"
            and item["labels"].get("task") == "sync"
            and item["labels"].get("error_type") == "WORKER_TASK_ERROR"
            for item in metrics["counters"]
        )


def test_execute_worker_task_dead_letters_when_create_task_run_fails_at_max_retries(
    session_factory: Any, monkeypatch: Any
) -> None:
    """PL-002: once retries are exhausted, a create_task_run DB failure must
    dead-letter the task so it is recorded, not silently dropped."""
    monkeypatch.setenv("WORKER_MAX_RETRIES", "2")
    settings = load_settings()

    def _raise_create_task_run(*_args: Any, **_kwargs: Any) -> Any:
        raise OperationalError(
            "INSERT INTO task_runs ...",
            {},
            RuntimeError("task_runs insert failed"),
        )

    monkeypatch.setattr(worker_task_execution, "create_task_run", _raise_create_task_run)

    with session_factory() as db:
        result = execute_worker_task(
            settings=settings,
            db=db,
            worker_token="worker:test",
            doc_id=94,
            task_type="sync",
            task={"doc_id": 94, "task": "sync", "retry_count": 2},
            retry_attempt=2,
            dispatch_worker_task_fn=lambda **_kwargs: None,
            build_handler_fn=lambda *_args: None,
            process_vision_ocr_force_fn=lambda *_args, **_kwargs: None,
            process_full_doc_fn=lambda *_args, **_kwargs: None,
            set_task_checkpoint_fn=lambda *_args, **_kwargs: None,
            logger=logging.getLogger(__name__),
        )

        # Retries exhausted -> dead-lettered, not re-enqueued.
        assert result["pending_retry_payload"] is None
        assert result["pending_retry_delay_seconds"] is None
        assert result["pending_dead_letter"] is not None
        dead_letter = result["pending_dead_letter"]
        assert dead_letter["task"] == {"doc_id": 94, "task": "sync", "retry_count": 2}
        assert dead_letter["error_type"] == "WORKER_TASK_ERROR"
        assert dead_letter["attempt"] == 3

        rows = db.query(TaskRun).filter(TaskRun.doc_id == 94).all()
        assert rows == []

        metrics = snapshot_metrics()
        assert any(
            item["name"] == "worker_task_dead_letters_total"
            and item["labels"].get("task") == "sync"
            and item["labels"].get("error_type") == "WORKER_TASK_ERROR"
            for item in metrics["counters"]
        )
