from __future__ import annotations

from typing import Any

from app.services.pipeline.task_runs import (
    create_task_run,
    find_latest_checkpoint,
    finish_task_run,
)
from app.services.pipeline.worker_checkpoint import (
    resume_stage_current,
    set_task_checkpoint,
)


def _checkpoint_current(payload: dict[str, Any] | None) -> int:
    return int((payload or {}).get("current") or 0)


def test_find_latest_checkpoint_excludes_completed_run_on_retry(
    session_factory: Any,
) -> None:
    """A completed run's terminal checkpoint (N/N) must not be inherited on retry.

    Regression for AUDIT PL-003: find_latest_checkpoint previously had no status
    filter, so a retried task could inherit a previously-completed run's
    terminal checkpoint (current == total), resume at start_index == total, and
    finish as a silent no-op success.
    """
    with session_factory() as db:
        # A previously completed page_notes run left a terminal checkpoint N/N.
        completed_run = create_task_run(
            db,
            doc_id=901,
            task="page_notes",
            source="vision_ocr",
            payload={"doc_id": 901, "task": "page_notes"},
            worker_id="worker:test",
            attempt=1,
        )
        set_task_checkpoint(
            db,
            run_id=int(completed_run.id),
            stage="page_notes",
            current=5,
            total=5,
            extra={"source": "vision_ocr"},
        )
        finish_task_run(
            db,
            run_id=int(completed_run.id),
            status="completed",
            duration_ms=800,
        )

    with session_factory() as db:
        # Default behavior is unchanged: the newest checkpoint of any status is
        # returned (pins backward compatibility with direct callers).
        default_checkpoint = find_latest_checkpoint(
            db,
            doc_id=901,
            task="page_notes",
            source="vision_ocr",
        )
        assert default_checkpoint is not None
        assert _checkpoint_current(default_checkpoint) == 5

        # The retry path opts in: the completed run's terminal checkpoint is
        # skipped, so no resume payload is inherited.
        retry_checkpoint = find_latest_checkpoint(
            db,
            doc_id=901,
            task="page_notes",
            source="vision_ocr",
            exclude_completed=True,
        )
        assert retry_checkpoint is None


def test_find_latest_checkpoint_still_returns_in_progress_retry_checkpoint(
    session_factory: Any,
) -> None:
    """exclude_completed must not discard a genuine in-progress retry checkpoint.

    A run that failed mid-way (status failed/retrying) and left a partial
    checkpoint (current < total) is the legitimate resume source for the next
    attempt; it must still be found.
    """
    with session_factory() as db:
        # A completed run first (older), then a failed in-progress run (newer).
        completed_run = create_task_run(
            db,
            doc_id=902,
            task="page_notes",
            source="vision_ocr",
            payload={"doc_id": 902, "task": "page_notes"},
            worker_id="worker:test",
            attempt=1,
        )
        set_task_checkpoint(
            db,
            run_id=int(completed_run.id),
            stage="page_notes",
            current=5,
            total=5,
            extra={"source": "vision_ocr"},
        )
        finish_task_run(
            db,
            run_id=int(completed_run.id),
            status="completed",
            duration_ms=800,
        )

        failed_run = create_task_run(
            db,
            doc_id=902,
            task="page_notes",
            source="vision_ocr",
            payload={"doc_id": 902, "task": "page_notes", "retry_count": 1},
            worker_id="worker:test",
            attempt=2,
        )
        set_task_checkpoint(
            db,
            run_id=int(failed_run.id),
            stage="page_notes",
            current=2,
            total=5,
            extra={"source": "vision_ocr"},
        )
        finish_task_run(
            db,
            run_id=int(failed_run.id),
            status="failed",
            duration_ms=900,
            error_type="LLM_TIMEOUT",
            error_message="temporary timeout",
        )

    with session_factory() as db:
        # The in-progress (failed) run's partial checkpoint is the newest
        # non-completed checkpoint and must be returned so the retry resumes
        # from page 2, not from the completed run's terminal N/N.
        checkpoint = find_latest_checkpoint(
            db,
            doc_id=902,
            task="page_notes",
            source="vision_ocr",
            exclude_completed=True,
        )
        assert checkpoint is not None
        assert _checkpoint_current(checkpoint) == 2
        # And it actually drives a real resume (not a no-op at start_index=total).
        assert resume_stage_current(
            checkpoint,
            stage="page_notes",
            source="vision_ocr",
            total=5,
        ) == 2
