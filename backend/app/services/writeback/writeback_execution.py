from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.api_models import WritebackDryRunCall, WritebackDryRunItem
from app.config import Settings
from app.models import SuggestionAudit, WritebackJob
from app.services.runtime.time_utils import utc_now_iso


def collect_changed_calls(
    *,
    preview_items: list[WritebackDryRunItem],
    build_calls_for_item: Callable[[WritebackDryRunItem], list[WritebackDryRunCall]],
) -> tuple[int, list[WritebackDryRunCall]]:
    calls: list[WritebackDryRunCall] = []
    docs_changed = 0
    for item in preview_items:
        if not item.changed:
            continue
        docs_changed += 1
        calls.extend(build_calls_for_item(item))
    return docs_changed, calls


def execute_calls_with_audit(
    *,
    settings: Settings,
    db: Session,
    calls: list[WritebackDryRunCall],
    dry_run: bool,
    execute_call: Callable[[Settings, Session, WritebackDryRunCall], None],
    cleanup_pending_rows_after_patch: Callable[[Session, int, dict[str, Any]], None],
    reviewed_timestamp_for_doc: Callable[[Settings, Session, int], str],
    logger: logging.Logger,
) -> set[int]:
    executed_doc_ids: set[int] = set()
    for call in calls:
        logger.info(
            "WRITEBACK %s doc=%s method=%s path=%s payload=%s",
            "DRY-RUN" if dry_run else "EXECUTE",
            call.doc_id,
            call.method,
            call.path,
            call.payload,
        )
        executed_doc_ids.add(int(call.doc_id))
        if dry_run:
            continue
        execute_call(settings, db, call)
        if call.method.upper() == "PATCH" and isinstance(call.payload, dict):
            cleanup_pending_rows_after_patch(db, int(call.doc_id), call.payload)

    if not dry_run and executed_doc_ids:
        for doc_id in sorted(executed_doc_ids):
            reviewed_at = reviewed_timestamp_for_doc(settings, db, int(doc_id))
            db.add(
                SuggestionAudit(
                    doc_id=int(doc_id),
                    action="apply_to_document:writeback",
                    source="writeback",
                    field=None,
                    old_value=None,
                    new_value=None,
                    created_at=reviewed_at,
                )
            )
    return executed_doc_ids


def run_writeback_job_execution(
    *,
    settings: Settings,
    db: Session,
    job: WritebackJob,
    dry_run: bool,
    deserialize_calls: Callable[[WritebackJob], list[WritebackDryRunCall]],
    execute_call: Callable[[Settings, Session, WritebackDryRunCall], None],
    cleanup_pending_rows_after_patch: Callable[[Session, int, dict[str, Any]], None],
    reviewed_timestamp_for_doc: Callable[[Settings, Session, int], str],
    missing_writeback_jobs_table: Callable[[Exception], bool],
    raise_missing_table_message: Callable[[], None],
    logger: logging.Logger,
) -> WritebackJob:
    job.started_at = utc_now_iso()
    job.status = "running"
    job.dry_run = bool(dry_run)
    try:
        db.commit()
    except (OperationalError, ProgrammingError) as exc:
        db.rollback()
        if missing_writeback_jobs_table(exc):
            raise_missing_table_message()
        raise

    execution_error: str | None = None
    calls = deserialize_calls(job)
    try:
        execute_calls_with_audit(
            settings=settings,
            db=db,
            calls=calls,
            dry_run=dry_run,
            execute_call=execute_call,
            cleanup_pending_rows_after_patch=cleanup_pending_rows_after_patch,
            reviewed_timestamp_for_doc=reviewed_timestamp_for_doc,
            logger=logger,
        )
    except Exception as exc:
        execution_error = str(exc)

    job.finished_at = utc_now_iso()
    if execution_error:
        job.status = "failed"
        job.error = execution_error
    else:
        job.status = "completed"
        job.error = None

    try:
        db.commit()
        db.refresh(job)
    except (OperationalError, ProgrammingError) as exc:
        db.rollback()
        if missing_writeback_jobs_table(exc):
            raise_missing_table_message()
        raise
    return job
