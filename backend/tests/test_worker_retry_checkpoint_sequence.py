from __future__ import annotations

from app.services.task_runs import create_task_run, find_latest_checkpoint, finish_task_run
from app.worker import _get_task_run_checkpoint, _resume_stage_current, _set_task_checkpoint


def test_worker_retry_checkpoint_continuation_for_mixed_task_sequence(session_factory):
    with session_factory() as db:
        # First task in sequence fails and leaves checkpoint progress.
        first_run = create_task_run(
            db,
            doc_id=801,
            task="vision_ocr",
            source="vision_ocr",
            payload={"doc_id": 801, "task": "vision_ocr"},
            worker_id="worker:test",
            attempt=1,
        )
        _set_task_checkpoint(
            db,
            run_id=int(first_run.id),
            stage="vision_ocr",
            current=3,
            total=10,
            extra={"source": "vision_ocr"},
        )
        finish_task_run(
            db,
            run_id=int(first_run.id),
            status="retrying",
            duration_ms=1200,
            error_type="LLM_TIMEOUT",
            error_message="temporary timeout",
        )

        previous_checkpoint = find_latest_checkpoint(
            db,
            doc_id=801,
            task="vision_ocr",
            source="vision_ocr",
        )
        assert previous_checkpoint is not None
        assert previous_checkpoint.get("current") == 3

        # Retry run carries resume payload and resumes from previous progress.
        retry_run = create_task_run(
            db,
            doc_id=801,
            task="vision_ocr",
            source="vision_ocr",
            payload={"doc_id": 801, "task": "vision_ocr", "retry_count": 1},
            worker_id="worker:test",
            attempt=2,
        )
        _set_task_checkpoint(
            db,
            run_id=int(retry_run.id),
            stage="resume",
            extra={"resume_from": previous_checkpoint},
        )
        retry_checkpoint = _get_task_run_checkpoint(db, run_id=int(retry_run.id))
        assert retry_checkpoint is not None
        assert retry_checkpoint.get("stage") == "resume"
        assert _resume_stage_current(
            retry_checkpoint,
            stage="vision_ocr",
            source="vision_ocr",
            total=10,
        ) == 3

        # Mixed sequence: a different task/source keeps independent checkpoint lineage.
        other_run = create_task_run(
            db,
            doc_id=801,
            task="embeddings_paperless",
            source="paperless_ocr",
            payload={"doc_id": 801, "task": "embeddings_paperless", "source": "paperless_ocr"},
            worker_id="worker:test",
            attempt=1,
        )
        _set_task_checkpoint(
            db,
            run_id=int(other_run.id),
            stage="embedding_chunks",
            current=8,
            total=20,
            extra={"source": "paperless_ocr"},
        )
        finish_task_run(
            db,
            run_id=int(other_run.id),
            status="completed",
            duration_ms=900,
            error_type=None,
            error_message=None,
        )

        same_family = find_latest_checkpoint(
            db,
            doc_id=801,
            task="vision_ocr",
            source="vision_ocr",
        )
        other_family = find_latest_checkpoint(
            db,
            doc_id=801,
            task="embeddings_paperless",
            source="paperless_ocr",
        )
        assert same_family is not None
        assert same_family.get("stage") == "resume"
        assert other_family is not None
        assert other_family.get("stage") == "embedding_chunks"
