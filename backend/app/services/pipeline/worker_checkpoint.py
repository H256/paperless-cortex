from __future__ import annotations

import json
import logging

from sqlalchemy.orm import Session

from app.models import TaskRun
from app.services.pipeline.task_runs import update_task_run_checkpoint

logger = logging.getLogger(__name__)


def set_task_checkpoint(
    db: Session,
    *,
    run_id: int | None,
    stage: str,
    current: int | None = None,
    total: int | None = None,
    extra: dict | None = None,
) -> None:
    if run_id is None:
        return
    payload: dict[str, object] = {"stage": stage}
    if current is not None:
        payload["current"] = int(current)
    if total is not None:
        payload["total"] = int(total)
    if extra:
        payload.update(extra)
    try:
        update_task_run_checkpoint(db, run_id=run_id, checkpoint=payload)
    except Exception:
        logger.warning("Failed to persist task checkpoint run_id=%s stage=%s", run_id, stage)


def get_task_run_checkpoint(db: Session, *, run_id: int | None) -> dict | None:
    if run_id is None:
        return None
    try:
        row = db.get(TaskRun, run_id)
    except Exception:
        # Worker must stay operational even when task-runs schema is not ready yet.
        logger.debug("Failed reading task run checkpoint run_id=%s", run_id, exc_info=True)
        return None
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


def resume_stage_current(
    checkpoint: dict | None,
    *,
    stage: str,
    source: str | None = None,
    total: int | None = None,
) -> int:
    if not checkpoint:
        return 0
    candidate = checkpoint
    resume_from = checkpoint.get("resume_from")
    if isinstance(resume_from, dict):
        candidate = resume_from
    if str(candidate.get("stage") or "").strip() != stage:
        return 0
    candidate_source = str(candidate.get("source") or "").strip()
    if source and candidate_source and candidate_source != source:
        return 0
    if total is not None:
        candidate_total = candidate.get("total")
        if isinstance(candidate_total, int) and candidate_total > 0 and candidate_total != total:
            return 0
    try:
        current = int(candidate.get("current") or 0)
    except Exception:
        return 0
    if total is not None:
        return max(0, min(current, int(total)))
    return max(0, current)
