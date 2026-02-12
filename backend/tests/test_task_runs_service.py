from __future__ import annotations

from app.models import TaskRun
from app.services.task_runs import find_latest_checkpoint


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
