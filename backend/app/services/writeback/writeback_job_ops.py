from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import HTTPException
from sqlalchemy.exc import OperationalError, ProgrammingError

from app.api_models import (
    WritebackHistoryResponse,
    WritebackJobDeleteResponse,
    WritebackJobDetail,
    WritebackJobListResponse,
)
from app.models import WritebackJob
from app.services.documents.cache_invalidation import invalidate_document_caches
from app.services.writeback.writeback_execution import run_writeback_job_execution
from app.services.writeback.writeback_jobs import (
    deserialize_calls,
    deserialize_doc_ids,
    job_detail,
    job_summary,
    missing_writeback_jobs_table,
    raise_missing_writeback_jobs_table,
)
from app.services.writeback.writeback_preview_cache import invalidate_writeback_preview_cache

if TYPE_CHECKING:
    import logging
    from collections.abc import Callable

    from sqlalchemy.orm import Session

    from app.api_models import WritebackDryRunCall
    from app.config import Settings


def list_jobs_response(db: Session, *, limit: int) -> WritebackJobListResponse:
    try:
        rows = (
            db.query(WritebackJob)
            .order_by(WritebackJob.id.desc())
            .limit(max(1, min(limit, 500)))
            .all()
        )
    except (OperationalError, ProgrammingError) as exc:
        if missing_writeback_jobs_table(exc):
            raise_missing_writeback_jobs_table()
        raise
    return WritebackJobListResponse(items=[job_summary(row) for row in rows])


def get_job_detail_response(db: Session, *, job_id: int) -> WritebackJobDetail:
    try:
        job = db.query(WritebackJob).filter(WritebackJob.id == job_id).first()
    except (OperationalError, ProgrammingError) as exc:
        if missing_writeback_jobs_table(exc):
            raise_missing_writeback_jobs_table()
        raise
    if not job:
        raise HTTPException(status_code=404, detail="Writeback job not found")
    return job_detail(job)


def delete_job_response(db: Session, *, job_id: int) -> WritebackJobDeleteResponse:
    try:
        job = db.query(WritebackJob).filter(WritebackJob.id == job_id).first()
    except (OperationalError, ProgrammingError) as exc:
        if missing_writeback_jobs_table(exc):
            raise_missing_writeback_jobs_table()
        raise
    if not job:
        return WritebackJobDeleteResponse(ok=True, removed=False, job_id=int(job_id))
    if str(job.status or "") == "running":
        raise HTTPException(status_code=409, detail="Cannot delete a running writeback job")
    db.delete(job)
    db.commit()
    return WritebackJobDeleteResponse(ok=True, removed=True, job_id=int(job_id))


def execute_job_response(
    settings: Settings,
    db: Session,
    *,
    job_id: int,
    dry_run: bool,
    execute_call: Callable[[Settings, Session, WritebackDryRunCall], None],
    cleanup_pending_rows_after_patch: Callable[[Session, int, dict[str, Any]], None],
    reviewed_timestamp_for_doc: Callable[[Settings, Session, int], str],
    logger: logging.Logger,
) -> WritebackJobDetail:
    try:
        job = db.query(WritebackJob).filter(WritebackJob.id == job_id).first()
    except (OperationalError, ProgrammingError) as exc:
        if missing_writeback_jobs_table(exc):
            raise_missing_writeback_jobs_table()
        raise
    if not job:
        raise HTTPException(status_code=404, detail="Writeback job not found")

    job = run_writeback_job_execution(
        settings=settings,
        db=db,
        job=job,
        dry_run=dry_run,
        deserialize_calls=deserialize_calls,
        execute_call=execute_call,
        cleanup_pending_rows_after_patch=cleanup_pending_rows_after_patch,
        reviewed_timestamp_for_doc=reviewed_timestamp_for_doc,
        missing_writeback_jobs_table=missing_writeback_jobs_table,
        raise_missing_table_message=raise_missing_writeback_jobs_table,
        logger=logger,
    )
    invalidate_writeback_preview_cache()
    job_doc_ids = deserialize_doc_ids(job)
    if job_doc_ids:
        for doc_id in job_doc_ids:
            invalidate_document_caches(int(doc_id))
    else:
        invalidate_document_caches()
    return job_detail(job)


def history_response(db: Session, *, limit: int) -> WritebackHistoryResponse:
    try:
        rows = (
            db.query(WritebackJob)
            .filter(WritebackJob.status.in_(["completed", "failed"]))
            .order_by(WritebackJob.id.desc())
            .limit(max(1, min(limit, 500)))
            .all()
        )
    except (OperationalError, ProgrammingError) as exc:
        if missing_writeback_jobs_table(exc):
            raise_missing_writeback_jobs_table()
        raise
    return WritebackHistoryResponse(items=[job_summary(row) for row in rows])
