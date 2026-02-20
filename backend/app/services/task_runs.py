from __future__ import annotations

import json
import logging
from typing import Any, Callable, TypeVar

from sqlalchemy.exc import PendingRollbackError
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models import TaskRun
from app.services.time_utils import utc_now_iso

logger = logging.getLogger(__name__)
T = TypeVar("T")


def _is_missing_task_runs_table_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "task_runs" in message and (
        "does not exist" in message or "undefinedtable" in message or "no such table" in message
    )


def _ensure_session_ready(db: Session) -> None:
    tx = db.get_transaction()
    if tx is not None and not tx.is_active:
        db.rollback()


def _run_with_pending_recovery(db: Session, *, context: str, operation: Callable[[], T]) -> T:
    _ensure_session_ready(db)
    try:
        return operation()
    except PendingRollbackError:
        logger.warning("Recovered pending rollback before %s; retrying", context)
        db.rollback()
        _ensure_session_ready(db)
        return operation()


def _run_task_runs_operation(
    db: Session,
    *,
    context: str,
    operation: Callable[[], T],
    on_missing_table: Callable[[], T] | None = None,
    missing_table_log: str | None = None,
) -> T:
    try:
        return _run_with_pending_recovery(db, context=context, operation=operation)
    except Exception as exc:
        db.rollback()
        if _is_missing_task_runs_table_error(exc) and on_missing_table is not None:
            if missing_table_log:
                logger.warning(missing_table_log)
            return on_missing_table()
        raise
def _build_task_runs_query(
    db: Session,
    *,
    doc_id: int | None = None,
    task: str | None = None,
    status: str | None = None,
    error_type: str | None = None,
    query_text: str | None = None,
):
    query = db.query(TaskRun)
    if doc_id is not None:
        query = query.filter(TaskRun.doc_id == doc_id)
    if task:
        query = query.filter(TaskRun.task == task)
    if status:
        query = query.filter(TaskRun.status == status)
    if error_type:
        query = query.filter(TaskRun.error_type == error_type)
    if query_text:
        needle = f"%{query_text.strip()}%"
        if needle != "%%":
            query = query.filter(
                or_(
                    TaskRun.task.ilike(needle),
                    TaskRun.source.ilike(needle),
                    TaskRun.status.ilike(needle),
                    TaskRun.error_type.ilike(needle),
                    TaskRun.error_message.ilike(needle),
                )
            )
    return query


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
    timestamp = utc_now_iso()
    row = TaskRun(
        doc_id=doc_id,
        task=task,
        source=source,
        status="running",
        worker_id=worker_id,
        payload_json=json.dumps(payload, ensure_ascii=False) if payload else None,
        checkpoint_json=None,
        attempt=max(1, int(attempt)),
        started_at=timestamp,
        created_at=timestamp,
        updated_at=timestamp,
    )

    def _create() -> TaskRun:
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    def _missing_row() -> TaskRun:
        row.id = 0
        return row

    return _run_task_runs_operation(
        db,
        context="create_task_run",
        operation=_create,
        on_missing_table=_missing_row,
        missing_table_log="task_runs table missing; skip create_task_run",
    )


def finish_task_run(
    db: Session,
    *,
    run_id: int,
    status: str,
    duration_ms: int | None,
    error_type: str | None = None,
    error_message: str | None = None,
) -> None:
    def _finish() -> None:
        row = db.get(TaskRun, run_id)
        if not row:
            return
        timestamp = utc_now_iso()
        row.status = status
        row.duration_ms = duration_ms
        row.error_type = error_type
        row.error_message = error_message
        row.finished_at = timestamp
        row.updated_at = timestamp
        db.commit()

    _run_task_runs_operation(
        db,
        context=f"finish_task_run run_id={run_id}",
        operation=_finish,
        on_missing_table=lambda: None,
        missing_table_log=f"task_runs table missing; skip finish_task_run run_id={run_id}",
    )


def update_task_run_checkpoint(
    db: Session,
    *,
    run_id: int,
    checkpoint: dict[str, Any],
) -> None:
    payload = json.dumps(checkpoint, ensure_ascii=False)

    def _update() -> None:
        row = db.get(TaskRun, run_id)
        if not row:
            return
        row.checkpoint_json = payload
        row.updated_at = utc_now_iso()
        db.commit()

    _run_task_runs_operation(
        db,
        context=f"update_task_run_checkpoint run_id={run_id}",
        operation=_update,
        on_missing_table=lambda: None,
        missing_table_log=f"task_runs table missing; skip checkpoint update run_id={run_id}",
    )


def list_task_runs(
    db: Session,
    *,
    doc_id: int | None = None,
    task: str | None = None,
    status: str | None = None,
    error_type: str | None = None,
    query_text: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[int, list[TaskRun]]:
    row_limit = max(1, min(int(limit), 1000))
    row_offset = max(0, int(offset))

    def _list() -> tuple[int, list[TaskRun]]:
        base_query = _build_task_runs_query(
            db,
            doc_id=doc_id,
            task=task,
            status=status,
            error_type=error_type,
            query_text=query_text,
        )
        rows_with_total = (
            base_query.with_entities(TaskRun, func.count(TaskRun.id).over().label("total_rows"))
            .order_by(TaskRun.id.desc())
            .offset(row_offset)
            .limit(row_limit)
            .all()
        )
        if rows_with_total:
            total = int(rows_with_total[0][1] or 0)
            rows = [row for row, _total in rows_with_total]
            return total, rows
        total = 0 if row_offset == 0 else int(base_query.count() or 0)
        rows: list[TaskRun] = []
        return total, rows

    return _run_task_runs_operation(
        db,
        context="list_task_runs",
        operation=_list,
        on_missing_table=lambda: (0, []),
        missing_table_log="task_runs table missing; return empty task-runs list",
    )


def find_latest_checkpoint(
    db: Session,
    *,
    doc_id: int,
    task: str,
    source: str | None = None,
) -> dict[str, Any] | None:
    def _find() -> dict[str, Any] | None:
        query = (
            db.query(TaskRun)
            .filter(
                TaskRun.doc_id == doc_id,
                TaskRun.task == task,
                TaskRun.checkpoint_json.isnot(None),
            )
            .order_by(TaskRun.id.desc())
        )
        if source:
            query = query.filter(TaskRun.source == source)
        row = query.first()
        if not row or not row.checkpoint_json:
            return None
        raw = str(row.checkpoint_json).strip()
        if not raw.startswith(("{", "[")):
            return None
        try:
            payload = json.loads(raw)
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None

    return _run_task_runs_operation(
        db,
        context="find_latest_checkpoint",
        operation=_find,
        on_missing_table=lambda: None,
        missing_table_log="task_runs table missing; no latest checkpoint available",
    )
