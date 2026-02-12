from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import TaskRun


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_task_run(
    db: Session,
    *,
    doc_id: int | None,
    task: str,
    source: str | None,
    payload: dict[str, Any] | None,
    worker_id: str | None,
    attempt: int = 1,
) -> TaskRun:
    timestamp = _now_iso()
    row = TaskRun(
        doc_id=doc_id,
        task=task,
        source=source,
        status="running",
        worker_id=worker_id,
        payload_json=json.dumps(payload, ensure_ascii=False) if payload else None,
        attempt=max(1, int(attempt)),
        started_at=timestamp,
        created_at=timestamp,
        updated_at=timestamp,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def finish_task_run(
    db: Session,
    *,
    run_id: int,
    status: str,
    duration_ms: int | None,
    error_type: str | None = None,
    error_message: str | None = None,
) -> None:
    row = db.get(TaskRun, run_id)
    if not row:
        return
    timestamp = _now_iso()
    row.status = status
    row.duration_ms = duration_ms
    row.error_type = error_type
    row.error_message = error_message
    row.finished_at = timestamp
    row.updated_at = timestamp
    db.commit()


def list_task_runs(
    db: Session,
    *,
    doc_id: int | None = None,
    task: str | None = None,
    status: str | None = None,
    error_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[int, list[TaskRun]]:
    query = db.query(TaskRun)
    if doc_id is not None:
        query = query.filter(TaskRun.doc_id == doc_id)
    if task:
        query = query.filter(TaskRun.task == task)
    if status:
        query = query.filter(TaskRun.status == status)
    if error_type:
        query = query.filter(TaskRun.error_type == error_type)
    total = query.count()
    rows = (
        query.order_by(TaskRun.id.desc())
        .offset(max(0, int(offset)))
        .limit(max(1, min(int(limit), 1000)))
        .all()
    )
    return total, rows
