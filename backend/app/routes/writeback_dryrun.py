from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session, selectinload

from app.api_models import (
    WritebackDirectExecuteRequest,
    WritebackDirectExecuteResponse,
    WritebackDryRunCall,
    WritebackDryRunExecuteRequest,
    WritebackDryRunExecuteResponse,
    WritebackDryRunPreviewResponse,
    WritebackExecuteNowRequest,
    WritebackExecuteNowResponse,
    WritebackExecutePendingJobResult,
    WritebackExecutePendingRequest,
    WritebackExecutePendingResponse,
    WritebackHistoryResponse,
    WritebackJobCreateRequest,
    WritebackJobDeleteResponse,
    WritebackJobDetail,
    WritebackJobExecuteRequest,
    WritebackJobListResponse,
    WritebackJobSummary,
)
from app.db import get_db
from app.deps import get_settings
from app.models import (
    Document,
    DocumentPendingCorrespondent,
    DocumentPendingTag,
    SuggestionAudit,
    WritebackJob,
)
from app.services.integrations import paperless
from app.services.runtime.json_utils import parse_json_list
from app.services.runtime.string_list_json import parse_string_list_json
from app.services.runtime.time_utils import utc_now_iso
from app.services.writeback.writeback_apply import execute_writeback_call as _execute_call
from app.services.writeback.writeback_direct import (
    build_writeback_conflicts as _build_writeback_conflicts,
)
from app.services.writeback.writeback_direct import (
    execute_direct_selection as _execute_direct_selection,
)
from app.services.writeback.writeback_direct import (
    resolve_direct_selection as _resolve_direct_selection,
)
from app.services.writeback.writeback_direct import (
    sync_local_field_from_paperless as _sync_local_field_from_paperless,
)
from app.services.writeback.writeback_execution import (
    collect_changed_calls,
    execute_calls_with_audit,
    run_writeback_job_execution,
)
from app.services.writeback.writeback_plan import extract_ai_summary_note
from app.services.writeback.writeback_preview import (
    build_writeback_item as _build_item,
)
from app.services.writeback.writeback_preview import (
    local_writeback_candidate_doc_ids as _local_writeback_candidate_doc_ids,
)
from app.services.writeback.writeback_preview import (
    metadata_maps as _metadata_maps,
)
from app.services.writeback.writeback_preview import (
    preview_for_doc_ids as _preview_for_doc_ids,
)
from app.services.writeback.writeback_selection import build_calls_for_item as _build_calls_for_item

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/writeback", tags=["writeback"])


def _missing_writeback_jobs_table(exc: Exception) -> bool:
    text = str(exc).lower()
    return "writeback_jobs" in text and (
        "no such table" in text
        or "does not exist" in text
        or "undefined table" in text
    )


def _raise_missing_table_message() -> None:
    raise HTTPException(
        status_code=503,
        detail="Writeback jobs table is missing. Run database migrations (alembic upgrade head).",
    )


def _cleanup_pending_rows_after_patch(
    db: Session, doc_id: int, patch_payload: dict[str, Any]
) -> None:
    if "tags" in patch_payload:
        pending_row = (
            db.query(DocumentPendingTag)
            .filter(DocumentPendingTag.doc_id == int(doc_id))
            .one_or_none()
        )
        if pending_row:
            db.delete(pending_row)
    if "correspondent" in patch_payload:
        pending_corr_row = (
            db.query(DocumentPendingCorrespondent)
            .filter(DocumentPendingCorrespondent.doc_id == int(doc_id))
            .one_or_none()
        )
        if pending_corr_row:
            db.delete(pending_corr_row)


def _job_summary(job: WritebackJob) -> WritebackJobSummary:
    return WritebackJobSummary(
        id=job.id,
        status=job.status,
        dry_run=bool(job.dry_run),
        docs_selected=int(job.docs_selected or 0),
        docs_changed=int(job.docs_changed or 0),
        calls_count=int(job.calls_count or 0),
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        error=job.error,
    )


def _deserialize_doc_ids(job: WritebackJob) -> list[int]:
    doc_ids: list[int] = []
    for item in parse_json_list(job.doc_ids_json):
        try:
            doc_ids.append(int(item))
        except (TypeError, ValueError):
            continue
    return doc_ids


def _deserialize_calls(job: WritebackJob) -> list[WritebackDryRunCall]:
    calls: list[WritebackDryRunCall] = []
    for item in parse_json_list(job.calls_json):
        if not isinstance(item, dict):
            continue
        try:
            calls.append(WritebackDryRunCall(**item))
        except ValidationError:
            continue
    return calls


def _job_detail(job: WritebackJob) -> WritebackJobDetail:
    return WritebackJobDetail(
        **_job_summary(job).model_dump(),
        doc_ids=_deserialize_doc_ids(job),
        calls=_deserialize_calls(job),
    )


def _reviewed_timestamp_for_doc(settings: Settings, db: Session, doc_id: int) -> str:
    try:
        remote_doc = paperless.get_document(settings, int(doc_id))
        modified = str(remote_doc.get("modified") or "").strip()
        if modified:
            local_doc = db.get(Document, int(doc_id))
            if local_doc:
                local_doc.modified = modified
            return modified
    except (httpx.HTTPError, RuntimeError, ValueError):
        logger.warning("Failed to fetch paperless modified for reviewed_at doc=%s", doc_id)
    return utc_now_iso()


@router.post("/documents/{doc_id}/execute-direct", response_model=WritebackDirectExecuteResponse)
def execute_writeback_direct_for_document(
    doc_id: int,
    request: WritebackDirectExecuteRequest,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    if not settings.writeback_execute_enabled:
        raise HTTPException(
            status_code=400,
            detail="Real writeback execution is disabled. Set WRITEBACK_EXECUTE_ENABLED=1 to enable it.",
        )
    local_doc = (
        db.query(Document)
        .options(selectinload(Document.tags), selectinload(Document.notes))
        .filter(Document.id == doc_id)
        .first()
    )
    if not local_doc:
        raise HTTPException(status_code=404, detail="Local document not found")
    correspondents_by_id, tags_by_id = _metadata_maps(db)
    pending_row = (
        db.query(DocumentPendingTag)
        .filter(DocumentPendingTag.doc_id == int(doc_id))
        .one_or_none()
    )
    pending_tag_names: list[str] = []
    if pending_row and pending_row.names_json:
        pending_tag_names = parse_string_list_json(pending_row.names_json)
    pending_correspondent_row = (
        db.query(DocumentPendingCorrespondent)
        .filter(DocumentPendingCorrespondent.doc_id == int(doc_id))
        .one_or_none()
    )
    pending_correspondent_name = (
        str(pending_correspondent_row.name or "").strip()
        if pending_correspondent_row
        else ""
    )
    remote_doc = paperless.get_document_cached(settings, doc_id)
    item = _build_item(
        local_doc=local_doc,
        remote_doc=remote_doc,
        correspondents_by_id=correspondents_by_id,
        tags_by_id=tags_by_id,
        pending_tag_names=pending_tag_names,
        pending_correspondent_name=pending_correspondent_name,
    )
    if not item.changed:
        reviewed_at = _reviewed_timestamp_for_doc(settings, db, int(doc_id))
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
        db.commit()
        return WritebackDirectExecuteResponse(
            status="no_changes",
            docs_changed=0,
            calls_count=0,
            doc_ids=[],
            calls=[],
            conflicts=[],
        )

    known_modified = (request.known_paperless_modified or "").strip()
    current_modified = str(remote_doc.get("modified") or "").strip()
    needs_conflict_resolution = bool(
        known_modified and current_modified and known_modified != current_modified
    )
    if needs_conflict_resolution and not request.resolutions:
        return WritebackDirectExecuteResponse(
            status="conflicts",
            docs_changed=len(item.changed_fields),
            calls_count=0,
            doc_ids=[],
            calls=[],
            conflicts=_build_writeback_conflicts(item),
        )

    resolutions = {str(k): str(v) for k, v in (request.resolutions or {}).items()}
    selection = _resolve_direct_selection(
        db=db,
        local_doc=local_doc,
        remote_doc=remote_doc,
        item=item,
        resolutions=resolutions,
        needs_conflict_resolution=needs_conflict_resolution,
        sync_local_field_from_paperless_fn=lambda inner_db, inner_local_doc, inner_remote_doc, field: _sync_local_field_from_paperless(
            inner_db,
            inner_local_doc,
            inner_remote_doc,
            field,
            extract_ai_summary_note=extract_ai_summary_note,
        ),
    )

    try:
        calls = _execute_direct_selection(
            settings=settings,
            db=db,
            doc_id=doc_id,
            selection=selection,
            execute_call_fn=_execute_call,
            cleanup_pending_rows_after_patch_fn=_cleanup_pending_rows_after_patch,
        )
    except RuntimeError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if calls or request.resolutions:
        reviewed_at = _reviewed_timestamp_for_doc(settings, db, int(doc_id))
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
    db.commit()
    return WritebackDirectExecuteResponse(
        status="completed",
        docs_changed=len(item.changed_fields),
        calls_count=len(calls),
        doc_ids=[doc_id] if calls else [],
        calls=calls,
        conflicts=[],
    )


@router.post("/execute-now", response_model=WritebackExecuteNowResponse)
def execute_writeback_now(
    request: WritebackExecuteNowRequest,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    if not settings.writeback_execute_enabled:
        raise HTTPException(
            status_code=400,
            detail="Real writeback execution is disabled. Set WRITEBACK_EXECUTE_ENABLED=1 to enable it.",
        )
    doc_ids = sorted({int(doc_id) for doc_id in request.doc_ids if int(doc_id) > 0})
    if not doc_ids:
        raise HTTPException(status_code=400, detail="No valid doc_ids provided")

    preview_items = _preview_for_doc_ids(settings, db, doc_ids)
    docs_changed, calls = collect_changed_calls(
        preview_items=preview_items,
        build_calls_for_item=_build_calls_for_item,
    )
    executed_doc_ids = execute_calls_with_audit(
        settings=settings,
        db=db,
        calls=calls,
        dry_run=False,
        execute_call=_execute_call,
        cleanup_pending_rows_after_patch=_cleanup_pending_rows_after_patch,
        reviewed_timestamp_for_doc=_reviewed_timestamp_for_doc,
        logger=logger,
    )
    db.commit()

    return WritebackExecuteNowResponse(
        docs_selected=len(doc_ids),
        docs_changed=docs_changed,
        calls_count=len(calls),
        doc_ids=sorted(executed_doc_ids),
        calls=calls,
    )


@router.get("/dry-run/preview", response_model=WritebackDryRunPreviewResponse)
def dry_run_preview(
    page: int = 1,
    page_size: int = 20,
    only_changed: bool = True,
    doc_id: int | None = None,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    """Preview pending writeback changes for one document or a paged selection."""
    if doc_id is not None and doc_id > 0:
        doc_ids = [int(doc_id)]
        total_count = 1
    elif only_changed:
        candidate_ids = _local_writeback_candidate_doc_ids(db)
        total_count = len(candidate_ids)
        start = max(0, (max(1, page) - 1) * max(1, page_size))
        end = start + max(1, page_size)
        doc_ids = candidate_ids[start:end]
    else:
        payload = paperless.list_documents_cached(settings, page=page, page_size=page_size)
        results = payload.get("results") or []
        doc_ids = [int(doc["id"]) for doc in results if isinstance(doc.get("id"), int)]
        total_count = int(payload.get("count") or 0)

    items = _preview_for_doc_ids(settings, db, doc_ids)
    if only_changed:
        items = [item for item in items if item.changed]
    return WritebackDryRunPreviewResponse(
        count=total_count,
        page=page,
        page_size=page_size,
        items=items,
    )


@router.post("/dry-run/execute", response_model=WritebackDryRunExecuteResponse)
def dry_run_execute(
    request: WritebackDryRunExecuteRequest,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    preview_items = _preview_for_doc_ids(settings, db, [int(doc_id) for doc_id in request.doc_ids])
    calls: list[WritebackDryRunCall] = []
    docs_changed = 0

    for item in preview_items:
        if not item.changed:
            continue
        docs_changed += 1
        item_calls = _build_calls_for_item(item)
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
        docs_selected=len(request.doc_ids),
        docs_changed=docs_changed,
        calls=calls,
    )


@router.post("/jobs", response_model=WritebackJobDetail)
def create_writeback_job(
    request: WritebackJobCreateRequest,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    """Create a persisted writeback job from the current previewable changes."""
    doc_ids = sorted({int(doc_id) for doc_id in request.doc_ids if int(doc_id) > 0})
    if not doc_ids:
        raise HTTPException(status_code=400, detail="No valid doc_ids provided")
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
        return _job_detail(existing)

    preview_items = _preview_for_doc_ids(settings, db, doc_ids)
    calls: list[WritebackDryRunCall] = []
    docs_changed = 0
    for item in preview_items:
        if not item.changed:
            continue
        docs_changed += 1
        calls.extend(_build_calls_for_item(item))
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
        if _missing_writeback_jobs_table(exc):
            _raise_missing_table_message()
        raise
    return _job_detail(job)


@router.get("/jobs", response_model=WritebackJobListResponse)
def list_writeback_jobs(db: Session = Depends(get_db), limit: int = 100):
    try:
        rows = (
            db.query(WritebackJob)
            .order_by(WritebackJob.id.desc())
            .limit(max(1, min(limit, 500)))
            .all()
        )
    except (OperationalError, ProgrammingError) as exc:
        if _missing_writeback_jobs_table(exc):
            _raise_missing_table_message()
        raise
    return WritebackJobListResponse(items=[_job_summary(row) for row in rows])


@router.get("/jobs/{job_id}", response_model=WritebackJobDetail)
def get_writeback_job(job_id: int, db: Session = Depends(get_db)):
    try:
        job = db.query(WritebackJob).filter(WritebackJob.id == job_id).first()
    except (OperationalError, ProgrammingError) as exc:
        if _missing_writeback_jobs_table(exc):
            _raise_missing_table_message()
        raise
    if not job:
        raise HTTPException(status_code=404, detail="Writeback job not found")
    return _job_detail(job)


@router.delete("/jobs/{job_id}", response_model=WritebackJobDeleteResponse)
def delete_writeback_job(job_id: int, db: Session = Depends(get_db)):
    try:
        job = db.query(WritebackJob).filter(WritebackJob.id == job_id).first()
    except (OperationalError, ProgrammingError) as exc:
        if _missing_writeback_jobs_table(exc):
            _raise_missing_table_message()
        raise
    if not job:
        return WritebackJobDeleteResponse(ok=True, removed=False, job_id=int(job_id))
    if str(job.status or "") == "running":
        raise HTTPException(status_code=409, detail="Cannot delete a running writeback job")
    db.delete(job)
    db.commit()
    return WritebackJobDeleteResponse(ok=True, removed=True, job_id=int(job_id))


@router.post("/jobs/{job_id}/execute", response_model=WritebackJobDetail)
def execute_writeback_job(
    job_id: int,
    request: WritebackJobExecuteRequest,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    try:
        job = db.query(WritebackJob).filter(WritebackJob.id == job_id).first()
    except (OperationalError, ProgrammingError) as exc:
        if _missing_writeback_jobs_table(exc):
            _raise_missing_table_message()
        raise
    if not job:
        raise HTTPException(status_code=404, detail="Writeback job not found")

    if not request.dry_run and not settings.writeback_execute_enabled:
        raise HTTPException(
            status_code=400,
            detail="Real writeback execution is disabled. Set WRITEBACK_EXECUTE_ENABLED=1 to enable it.",
        )

    job = run_writeback_job_execution(
        settings=settings,
        db=db,
        job=job,
        dry_run=request.dry_run,
        deserialize_calls=_deserialize_calls,
        execute_call=_execute_call,
        cleanup_pending_rows_after_patch=_cleanup_pending_rows_after_patch,
        reviewed_timestamp_for_doc=_reviewed_timestamp_for_doc,
        missing_writeback_jobs_table=_missing_writeback_jobs_table,
        raise_missing_table_message=_raise_missing_table_message,
        logger=logger,
    )
    return _job_detail(job)


@router.get("/history", response_model=WritebackHistoryResponse)
def writeback_history(db: Session = Depends(get_db), limit: int = 100):
    try:
        rows = (
            db.query(WritebackJob)
            .filter(WritebackJob.status.in_(["completed", "failed"]))
            .order_by(WritebackJob.id.desc())
            .limit(max(1, min(limit, 500)))
            .all()
        )
    except (OperationalError, ProgrammingError) as exc:
        if _missing_writeback_jobs_table(exc):
            _raise_missing_table_message()
        raise
    return WritebackHistoryResponse(items=[_job_summary(row) for row in rows])


@router.post("/jobs/execute-pending", response_model=WritebackExecutePendingResponse)
def execute_pending_writeback_jobs(
    request: WritebackExecutePendingRequest,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    if not request.dry_run and not settings.writeback_execute_enabled:
        raise HTTPException(
            status_code=400,
            detail="Real writeback execution is disabled. Set WRITEBACK_EXECUTE_ENABLED=1 to enable it.",
        )

    limit = max(0, int(request.limit or 0))
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
            dry_run=request.dry_run,
            deserialize_calls=_deserialize_calls,
            execute_call=_execute_call,
            cleanup_pending_rows_after_patch=_cleanup_pending_rows_after_patch,
            reviewed_timestamp_for_doc=_reviewed_timestamp_for_doc,
            missing_writeback_jobs_table=_missing_writeback_jobs_table,
            raise_missing_table_message=_raise_missing_table_message,
            logger=logger,
        )
        result_doc_ids = _deserialize_doc_ids(result)
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

    return WritebackExecutePendingResponse(
        processed=len(processed_ids),
        completed=completed,
        failed=failed,
        job_ids=processed_ids,
        doc_ids=sorted(processed_doc_ids),
        results=job_results,
    )
