from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.exc import PendingRollbackError
from sqlalchemy.orm import Session

from app.models import TaskRun

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_missing_task_runs_table_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "task_runs" in message and (
        "does not exist" in message
        or "undefinedtable" in message
        or "no such table" in message
    )


def _ensure_session_ready(db: Session) -> None:
    tx = db.get_transaction()
    if tx is not None and not tx.is_active:
        db.rollback()


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
    _ensure_session_ready(db)
    timestamp = _now_iso()
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
    try:
        db.add(row)
        db.commit()
        db.refresh(row)
    except Exception as exc:
        db.rollback()
        if isinstance(exc, PendingRollbackError):
            logger.warning("Recovered pending rollback before create_task_run; retrying")
            _ensure_session_ready(db)
            db.add(row)
            db.commit()
            db.refresh(row)
            return row
        if _is_missing_task_runs_table_error(exc):
            logger.warning("task_runs table missing; skip create_task_run")
            row.id = 0
            return row
        raise
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
    _ensure_session_ready(db)
    try:
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
    except Exception as exc:
        db.rollback()
        if isinstance(exc, PendingRollbackError):
            logger.warning("Recovered pending rollback before finish_task_run run_id=%s", run_id)
            _ensure_session_ready(db)
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
            return
        if _is_missing_task_runs_table_error(exc):
            logger.warning("task_runs table missing; skip finish_task_run run_id=%s", run_id)
            return
        raise


def update_task_run_checkpoint(
    db: Session,
    *,
    run_id: int,
    checkpoint: dict[str, Any],
) -> None:
    _ensure_session_ready(db)
    try:
        row = db.get(TaskRun, run_id)
        if not row:
            return
        row.checkpoint_json = json.dumps(checkpoint, ensure_ascii=False)
        row.updated_at = _now_iso()
        db.commit()
    except Exception as exc:
        db.rollback()
        if isinstance(exc, PendingRollbackError):
            logger.warning("Recovered pending rollback before checkpoint update run_id=%s", run_id)
            _ensure_session_ready(db)
            row = db.get(TaskRun, run_id)
            if not row:
                return
            row.checkpoint_json = json.dumps(checkpoint, ensure_ascii=False)
            row.updated_at = _now_iso()
            db.commit()
            return
        if _is_missing_task_runs_table_error(exc):
            logger.warning("task_runs table missing; skip checkpoint update run_id=%s", run_id)
            return
        raise


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
    _ensure_session_ready(db)
    try:
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
    except Exception as exc:
        db.rollback()
        if isinstance(exc, PendingRollbackError):
            logger.warning("Recovered pending rollback before list_task_runs; retrying")
            _ensure_session_ready(db)
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
        if _is_missing_task_runs_table_error(exc):
            logger.warning("task_runs table missing; return empty task-runs list")
            return 0, []
        raise


def find_latest_checkpoint(
    db: Session,
    *,
    doc_id: int,
    task: str,
    source: str | None = None,
) -> dict[str, Any] | None:
    _ensure_session_ready(db)
    try:
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
        if not isinstance(payload, dict):
            return None
        return payload
    except Exception as exc:
        db.rollback()
        if isinstance(exc, PendingRollbackError):
            logger.warning("Recovered pending rollback before find_latest_checkpoint")
            _ensure_session_ready(db)
            return find_latest_checkpoint(db, doc_id=doc_id, task=task, source=source)
        if _is_missing_task_runs_table_error(exc):
            logger.warning("task_runs table missing; no latest checkpoint available")
            return None
        raise
