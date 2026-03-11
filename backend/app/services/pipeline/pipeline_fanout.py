from __future__ import annotations

import json
from json import JSONDecodeError
from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, or_

from app.models import TaskRun

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.orm import Session


def latest_task_runs_by_signature(
    db: Session,
    *,
    doc_id: int,
    signatures: set[tuple[str, str]] | None = None,
) -> dict[tuple[str, str], TaskRun]:
    query = db.query(TaskRun).filter(TaskRun.doc_id == int(doc_id))
    if signatures:
        signature_filters = []
        for task, source in signatures:
            if not task:
                continue
            if source:
                signature_filters.append(and_(TaskRun.task == task, TaskRun.source == source))
            else:
                signature_filters.append(and_(TaskRun.task == task, or_(TaskRun.source.is_(None), TaskRun.source == "")))
        if signature_filters:
            query = query.filter(or_(*signature_filters))

    latest: dict[tuple[str, str], TaskRun] = {}
    for row in query.order_by(TaskRun.id.desc()).yield_per(200):
        key = (str(row.task or "").strip(), str(row.source or "").strip())
        if key in latest:
            continue
        latest[key] = row
        if signatures and len(latest) >= len(signatures):
            break
    return latest


def fanout_status_from_run(*, is_missing: bool, run: TaskRun | None) -> str:
    if run and str(run.status or "") in {"running", "retrying"}:
        return str(run.status)
    if run and str(run.status or "") == "failed":
        return "failed"
    if is_missing:
        return "missing"
    return "done"


def _checkpoint_from_run(run: TaskRun | None) -> dict[str, Any] | None:
    if not run or not run.checkpoint_json:
        return None
    raw = str(run.checkpoint_json).strip()
    if not raw.startswith(("{", "[")):
        return None
    try:
        parsed = json.loads(raw)
    except JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def build_pipeline_fanout_items(
    *,
    planned_tasks: list[dict[str, Any]],
    missing_signatures: set[tuple[str, str]],
    latest_runs: dict[tuple[str, str], TaskRun],
    signature_for_task: Callable[[dict[str, Any]], tuple[str, str]],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for index, task in enumerate(planned_tasks, start=1):
        signature = signature_for_task(task)
        run = latest_runs.get(signature)
        items.append(
            {
                "order": index,
                "task": str(task.get("task") or ""),
                "source": task.get("source"),
                "status": fanout_status_from_run(is_missing=signature in missing_signatures, run=run),
                "detail": f"{task['task']} ({task.get('source') or 'default'})",
                "checkpoint": _checkpoint_from_run(run),
                "error_type": run.error_type if run else None,
                "error_message": run.error_message if run else None,
                "last_started_at": run.started_at if run else None,
                "last_finished_at": run.finished_at if run else None,
            }
        )
    return items
