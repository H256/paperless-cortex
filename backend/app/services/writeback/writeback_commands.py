from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException
from sqlalchemy.exc import OperationalError, ProgrammingError

from app.api_models import (
    WritebackDryRunCall,
    WritebackDryRunExecuteResponse,
    WritebackExecuteNowResponse,
    WritebackExecutePendingJobResult,
    WritebackExecutePendingResponse,
    WritebackJobDetail,
)
from app.models import WritebackJob
from app.services.documents.documents_list_cache import invalidate_documents_list_cache
from app.services.documents.local_document_cache import invalidate_local_document_cache
from app.services.runtime.time_utils import utc_now_iso
from app.services.writeback.writeback_execution import (
    collect_changed_calls,
    execute_calls_with_audit,
    run_writeback_job_execution,
)
from app.services.writeback.writeback_jobs import (
    deserialize_calls,
    deserialize_doc_ids,
    job_detail,
    missing_writeback_jobs_table,
    raise_missing_writeback_jobs_table,
)
from app.services.writeback.writeback_preview import preview_for_doc_ids
from app.services.writeback.writeback_preview_cache import (
    get_cached_writeback_preview,
    invalidate_writeback_preview_cache,
)
from app.services.writeback.writeback_selection import build_calls_for_item

if TYPE_CHECKING:
    import logging
    from collections.abc import Callable

    from sqlalchemy.orm import Session

    from app.config import Settings


def execute_now_response(
    settings: Settings,
    db: Session,
    *,
    doc_ids: list[int],
    execute_call: Callable[[Settings, Session, WritebackDryRunCall], None],
    cleanup_pending_rows_after_patch: Callable[[Session, int, dict[str, Any]], None],
    reviewed_timestamp_for_doc: Callable[[Settings, Session, int], str],
    logger: logging.Logger,
) -> WritebackExecuteNowResponse:
    preview_items = get_cached_writeback_preview(
        doc_ids=doc_ids,
        build_preview=lambda: preview_for_doc_ids(settings, db, doc_ids),
    )
    docs_changed, calls = collect_changed_calls(
        preview_items=preview_items,
        build_calls_for_item=build_calls_for_item,
    )
    executed_doc_ids = execute_calls_with_audit(
        settings=settings,
        db=db,
        calls=calls,
        dry_run=False,
        execute_call=execute_call,
        cleanup_pending_rows_after_patch=cleanup_pending_rows_after_patch,
        reviewed_timestamp_for_doc=reviewed_timestamp_for_doc,
        logger=logger,
    )
    db.commit()
    invalidate_writeback_preview_cache()
    invalidate_documents_list_cache()
    for doc_id in executed_doc_ids:
        invalidate_local_document_cache(int(doc_id))
    return WritebackExecuteNowResponse(
        docs_selected=len(doc_ids),
        docs_changed=docs_changed,
        calls_count=len(calls),
        doc_ids=sorted(executed_doc_ids),
        calls=calls,
    )


def dry_run_execute_response(
    settings: Settings,
    db: Session,
    *,
    doc_ids: list[int],
    logger: logging.Logger,
) -> WritebackDryRunExecuteResponse:
    preview_items = get_cached_writeback_preview(
        doc_ids=doc_ids,
        build_preview=lambda: preview_for_doc_ids(settings, db, doc_ids),
    )
    calls: list[WritebackDryRunCall] = []
    docs_changed = 0
    for item in preview_items:
        if not item.changed:
            continue
        docs_changed += 1
        item_calls = build_calls_for_item(item)
        calls.extend(item_calls)
        for call in item_calls:
            logger.info(
                "DRY-RUN writeback doc=%s method=%s path=%s payload=%s",
                call.doc_id,
                call.method,
                call.path,
                call.payload,
            )
    return WritebackDryRunExecuteResponse(
        docs_selected=len(doc_ids),
        docs_changed=docs_changed,
        calls=calls,
    )


def create_job_response(
    settings: Settings,
    db: Session,
    *,
    doc_ids: list[int],
) -> WritebackJobDetail:
    doc_ids_json = json.dumps(doc_ids)
    existing = (
        db.query(WritebackJob)
        .filter(
            WritebackJob.status.in_(["pending", "running"]),
            WritebackJob.doc_ids_json == doc_ids_json,
        )
        .order_by(WritebackJob.id.desc())
        .first()
    )
    if existing:
        return job_detail(existing)

    preview_items = get_cached_writeback_preview(
        doc_ids=doc_ids,
        build_preview=lambda: preview_for_doc_ids(settings, db, doc_ids),
    )
    calls: list[WritebackDryRunCall] = []
    docs_changed = 0
    for item in preview_items:
        if not item.changed:
            continue
        docs_changed += 1
        calls.extend(build_calls_for_item(item))
    if docs_changed == 0:
        raise HTTPException(
            status_code=400,
            detail="No writeback changes detected for selected documents.",
        )

    job = WritebackJob(
        status="pending",
        dry_run=True,
        docs_selected=len(doc_ids),
        docs_changed=docs_changed,
        calls_count=len(calls),
        doc_ids_json=doc_ids_json,
        calls_json=json.dumps([call.model_dump() for call in calls]),
        created_at=utc_now_iso(),
    )
    try:
        db.add(job)
        db.commit()
        db.refresh(job)
    except (OperationalError, ProgrammingError) as exc:
        db.rollback()
        if missing_writeback_jobs_table(exc):
            raise_missing_writeback_jobs_table()
        raise
    return job_detail(job)


def execute_pending_jobs_response(
    settings: Settings,
    db: Session,
    *,
    dry_run: bool,
    limit: int,
    execute_call: Callable[[Settings, Session, WritebackDryRunCall], None],
    cleanup_pending_rows_after_patch: Callable[[Session, int, dict[str, Any]], None],
    reviewed_timestamp_for_doc: Callable[[Settings, Session, int], str],
    logger: logging.Logger,
) -> WritebackExecutePendingResponse:
    query = (
        db.query(WritebackJob)
        .filter(WritebackJob.status == "pending")
        .order_by(WritebackJob.id.asc())
    )
    if limit > 0:
        query = query.limit(limit)

    completed = 0
    failed = 0
    processed_ids: list[int] = []
    processed_doc_ids: set[int] = set()
    job_results: list[WritebackExecutePendingJobResult] = []
    for index, job in enumerate(query.yield_per(50), start=1):
        if limit > 0 and index > limit:
            break
        processed_ids.append(int(job.id))
        result = run_writeback_job_execution(
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
        result_doc_ids = deserialize_doc_ids(result)
        for doc_id in result_doc_ids:
            processed_doc_ids.add(int(doc_id))
        job_results.append(
            WritebackExecutePendingJobResult(
                job_id=int(result.id),
                status=result.status,
                dry_run=bool(result.dry_run),
                docs_selected=int(result.docs_selected or 0),
                docs_changed=int(result.docs_changed or 0),
                calls_count=int(result.calls_count or 0),
                doc_ids=result_doc_ids,
                error=result.error,
            )
        )
        if result.status == "completed":
            completed += 1
        else:
            failed += 1
    if processed_ids:
        invalidate_writeback_preview_cache()
        invalidate_documents_list_cache()
        for doc_id in processed_doc_ids:
            invalidate_local_document_cache(int(doc_id))

    return WritebackExecutePendingResponse(
        processed=len(processed_ids),
        completed=completed,
        failed=failed,
        job_ids=processed_ids,
        doc_ids=sorted(processed_doc_ids),
        results=job_results,
    )
