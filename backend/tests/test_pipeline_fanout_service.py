from __future__ import annotations

from app.models import TaskRun
from app.services.pipeline.pipeline_fanout import (
    build_pipeline_fanout_items,
    fanout_status_from_run,
    latest_task_runs_by_signature,
)


def test_fanout_status_from_run_prioritizes_run_state():
    running = TaskRun(task="vision_ocr", status="running")
    failed = TaskRun(task="vision_ocr", status="failed")

    assert fanout_status_from_run(is_missing=True, run=running) == "running"
    assert fanout_status_from_run(is_missing=True, run=failed) == "failed"
    assert fanout_status_from_run(is_missing=True, run=None) == "missing"
    assert fanout_status_from_run(is_missing=False, run=None) == "done"


def test_build_pipeline_fanout_items_includes_checkpoint_and_run_metadata():
    planned = [{"doc_id": 1, "task": "vision_ocr", "source": "vision_ocr"}]
    run = TaskRun(
        task="vision_ocr",
        source="vision_ocr",
        status="running",
        checkpoint_json='{"current":1,"total":10}',
        error_type="runtime_error",
        error_message="partial failure",
        started_at="2026-02-20T10:00:00+00:00",
        finished_at=None,
    )
    latest_runs = {("vision_ocr", "vision_ocr"): run}

    items = build_pipeline_fanout_items(
        planned_tasks=planned,
        missing_signatures={("vision_ocr", "vision_ocr")},
        latest_runs=latest_runs,
        signature_for_task=lambda task: (str(task.get("task") or ""), str(task.get("source") or "")),
    )

    assert len(items) == 1
    item = items[0]
    assert item["order"] == 1
    assert item["task"] == "vision_ocr"
    assert item["source"] == "vision_ocr"
    assert item["status"] == "running"
    assert item["checkpoint"] == {"current": 1, "total": 10}
    assert item["error_type"] == "runtime_error"
    assert item["error_message"] == "partial failure"
    assert item["last_started_at"] == "2026-02-20T10:00:00+00:00"


def test_build_pipeline_fanout_items_ignores_non_object_checkpoint():
    planned = [{"doc_id": 1, "task": "sync"}]
    run = TaskRun(task="sync", source=None, status="done", checkpoint_json='["unexpected"]')
    latest_runs = {("sync", ""): run}

    items = build_pipeline_fanout_items(
        planned_tasks=planned,
        missing_signatures=set(),
        latest_runs=latest_runs,
        signature_for_task=lambda task: (str(task.get("task") or ""), str(task.get("source") or "")),
    )

    assert len(items) == 1
    assert items[0]["checkpoint"] is None
    assert items[0]["status"] == "done"


def test_latest_task_runs_by_signature_returns_latest_record_per_signature(session_factory):
    with session_factory() as db:
        db.add(TaskRun(doc_id=11, task="sync", source=None, status="done"))
        db.add(TaskRun(doc_id=11, task="sync", source=None, status="running"))
        db.add(TaskRun(doc_id=11, task="vision_ocr", source="vision_ocr", status="failed"))
        db.commit()

        latest = latest_task_runs_by_signature(
            db,
            doc_id=11,
            signatures={("sync", ""), ("vision_ocr", "vision_ocr")},
        )

        assert latest[("sync", "")].status == "running"
        assert latest[("vision_ocr", "vision_ocr")].status == "failed"
