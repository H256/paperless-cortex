from __future__ import annotations

from datetime import datetime, timezone
import logging
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session, joinedload

from app.api_models import (
    WritebackHistoryResponse,
    WritebackDryRunCall,
    WritebackDryRunExecuteRequest,
    WritebackDryRunExecuteResponse,
    WritebackJobCreateRequest,
    WritebackJobDetail,
    WritebackExecutePendingRequest,
    WritebackExecutePendingResponse,
    WritebackJobExecuteRequest,
    WritebackJobListResponse,
    WritebackJobSummary,
    WritebackDryRunItem,
    WritebackDryRunPreviewResponse,
    WritebackFieldDiff,
)
from app.config import Settings
from app.db import get_db
from app.deps import get_settings
from app.models import Correspondent, Document, Tag, WritebackJob
from app.services import paperless
from app.services.writeback_plan import compare_document_fields, extract_ai_summary_note

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/writeback", tags=["writeback"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _build_item(
    *,
    local_doc: Document,
    remote_doc: dict[str, Any],
    correspondents_by_id: dict[int, str],
    tags_by_id: dict[int, str],
) -> WritebackDryRunItem:
    remote_notes = remote_doc.get("notes") if isinstance(remote_doc.get("notes"), list) else []
    remote_note_id, remote_note_text = extract_ai_summary_note(remote_notes)
    local_note_id, local_note_text = extract_ai_summary_note(
        [{"id": row.id, "note": row.note} for row in (local_doc.notes or [])]
    )

    local_tags = sorted(tag.id for tag in (local_doc.tags or []))
    remote_tags_raw = remote_doc.get("tags") or []
    remote_tags = sorted(int(tag_id) for tag_id in remote_tags_raw if isinstance(tag_id, int))

    changed_fields, payload = compare_document_fields(
        local_title=local_doc.title,
        remote_title=remote_doc.get("title"),
        local_date=local_doc.document_date,
        remote_date=remote_doc.get("document_date"),
        local_correspondent_id=local_doc.correspondent_id,
        remote_correspondent_id=remote_doc.get("correspondent"),
        local_tags=local_tags,
        remote_tags=remote_tags,
        local_ai_note=local_note_text,
        remote_ai_note=remote_note_text,
    )

    remote_correspondent_id = remote_doc.get("correspondent")
    local_corr_name = correspondents_by_id.get(local_doc.correspondent_id or 0) if local_doc.correspondent_id else None
    remote_corr_name = (
        correspondents_by_id.get(int(remote_correspondent_id))
        if isinstance(remote_correspondent_id, int)
        else None
    )
    remote_tag_names = [tags_by_id.get(tag_id, str(tag_id)) for tag_id in remote_tags]
    local_tag_names = [tags_by_id.get(tag_id, str(tag_id)) for tag_id in local_tags]

    note_diff = WritebackFieldDiff(
        field="note",
        original=remote_note_text,
        proposed=local_note_text,
        changed="note" in changed_fields,
    )
    if payload.get("note_action"):
        note_diff = WritebackFieldDiff(
            field="note",
            original={"id": remote_note_id, "text": remote_note_text},
            proposed={"id": local_note_id, "text": local_note_text, "action": payload.get("note_action")},
            changed="note" in changed_fields,
        )

    return WritebackDryRunItem(
        doc_id=local_doc.id,
        changed=bool(changed_fields),
        changed_fields=changed_fields,
        title=WritebackFieldDiff(
            field="title",
            original=remote_doc.get("title"),
            proposed=local_doc.title,
            changed="title" in changed_fields,
        ),
        document_date=WritebackFieldDiff(
            field="document_date",
            original=remote_doc.get("document_date"),
            proposed=local_doc.document_date,
            changed="document_date" in changed_fields,
        ),
        correspondent=WritebackFieldDiff(
            field="correspondent",
            original={"id": remote_correspondent_id, "name": remote_corr_name},
            proposed={"id": local_doc.correspondent_id, "name": local_corr_name},
            changed="correspondent" in changed_fields,
        ),
        tags=WritebackFieldDiff(
            field="tags",
            original={"ids": remote_tags, "names": remote_tag_names},
            proposed={"ids": local_tags, "names": local_tag_names},
            changed="tags" in changed_fields,
        ),
        note=note_diff,
    )


def _preview_for_doc_ids(
    settings: Settings,
    db: Session,
    doc_ids: list[int],
) -> list[WritebackDryRunItem]:
    if not doc_ids:
        return []
    local_docs = (
        db.query(Document)
        .options(joinedload(Document.tags), joinedload(Document.notes))
        .filter(Document.id.in_(doc_ids))
        .all()
    )
    local_by_id = {doc.id: doc for doc in local_docs}
    if not local_by_id:
        return []

    correspondents_by_id = {
        row.id: (row.name or "")
        for row in db.query(Correspondent).all()
    }
    tags_by_id = {row.id: (row.name or "") for row in db.query(Tag).all()}

    items: list[WritebackDryRunItem] = []
    for doc_id in doc_ids:
        local_doc = local_by_id.get(doc_id)
        if not local_doc:
            continue
        remote_doc = paperless.get_document(settings, doc_id)
        items.append(
            _build_item(
                local_doc=local_doc,
                remote_doc=remote_doc,
                correspondents_by_id=correspondents_by_id,
                tags_by_id=tags_by_id,
            )
        )
    return items


def _build_calls_for_item(item: WritebackDryRunItem) -> list[WritebackDryRunCall]:
    calls: list[WritebackDryRunCall] = []
    if not item.changed:
        return calls

    payload: dict[str, Any] = {}
    if item.title.changed:
        payload["title"] = item.title.proposed
    if item.document_date.changed:
        payload["document_date"] = item.document_date.proposed
    if item.correspondent.changed and isinstance(item.correspondent.proposed, dict):
        payload["correspondent"] = item.correspondent.proposed.get("id")
    if item.tags.changed and isinstance(item.tags.proposed, dict):
        payload["tags"] = item.tags.proposed.get("ids") or []
    if payload:
        calls.append(
            WritebackDryRunCall(
                doc_id=item.doc_id,
                method="PATCH",
                path=f"/api/documents/{item.doc_id}/",
                payload=payload,
            )
        )

    if item.note.changed and isinstance(item.note.proposed, dict):
        proposed_text = str(item.note.proposed.get("text") or "")
        action = str(item.note.proposed.get("action") or "")
        original_note = item.note.original if isinstance(item.note.original, dict) else {}
        original_note_id = original_note.get("id")
        if action == "replace" and original_note_id:
            calls.append(
                WritebackDryRunCall(
                    doc_id=item.doc_id,
                    method="DELETE",
                    path=f"/api/documents/{item.doc_id}/notes/{int(original_note_id)}/",
                    payload={},
                )
            )
        calls.append(
            WritebackDryRunCall(
                doc_id=item.doc_id,
                method="POST",
                path=f"/api/documents/{item.doc_id}/notes/",
                payload={"note": proposed_text},
            )
        )
    return calls


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
    if not job.doc_ids_json:
        return []
    try:
        return [int(item) for item in json.loads(job.doc_ids_json)]
    except Exception:
        return []


def _deserialize_calls(job: WritebackJob) -> list[WritebackDryRunCall]:
    if not job.calls_json:
        return []
    try:
        return [WritebackDryRunCall(**item) for item in json.loads(job.calls_json)]
    except Exception:
        return []


def _job_detail(job: WritebackJob) -> WritebackJobDetail:
    return WritebackJobDetail(
        **_job_summary(job).model_dump(),
        doc_ids=_deserialize_doc_ids(job),
        calls=_deserialize_calls(job),
    )


def _execute_call(settings: Settings, call: WritebackDryRunCall) -> None:
    method = call.method.upper()
    if method == "PATCH":
        paperless.update_document(settings, int(call.doc_id), dict(call.payload or {}))
        return
    if method == "POST":
        payload = dict(call.payload or {})
        note = str(payload.get("note") or "")
        paperless.add_document_note(settings, int(call.doc_id), note)
        return
    if method == "DELETE":
        path = str(call.path or "")
        note_id: int | None = None
        try:
            segment = path.rstrip("/").split("/")[-1]
            note_id = int(segment)
        except Exception:
            note_id = None
        if note_id is None:
            raise RuntimeError(f"Cannot parse note id from path: {path}")
        paperless.delete_document_note(settings, int(call.doc_id), note_id)
        return
    raise RuntimeError(f"Unsupported writeback method: {method}")


def _run_job_execution(settings: Settings, db: Session, job: WritebackJob, dry_run: bool) -> WritebackJob:
    job.started_at = _now_iso()
    job.status = "running"
    job.dry_run = bool(dry_run)
    try:
        db.commit()
    except (OperationalError, ProgrammingError) as exc:
        db.rollback()
        if _missing_writeback_jobs_table(exc):
            _raise_missing_table_message()
        raise

    calls = _deserialize_calls(job)
    execution_error: str | None = None
    try:
        for call in calls:
            logger.info(
                "WRITEBACK %s doc=%s method=%s path=%s payload=%s",
                "DRY-RUN" if dry_run else "EXECUTE",
                call.doc_id,
                call.method,
                call.path,
                call.payload,
            )
            if not dry_run:
                _execute_call(settings, call)
    except Exception as exc:
        execution_error = str(exc)

    job.finished_at = _now_iso()
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
        if _missing_writeback_jobs_table(exc):
            _raise_missing_table_message()
        raise
    return job


@router.get("/dry-run/preview", response_model=WritebackDryRunPreviewResponse)
def dry_run_preview(
    page: int = 1,
    page_size: int = 20,
    only_changed: bool = True,
    doc_id: int | None = None,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    if doc_id is not None and doc_id > 0:
        doc_ids = [int(doc_id)]
        total_count = 1
    else:
        payload = paperless.list_documents(settings, page=page, page_size=page_size)
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
    doc_ids = sorted({int(doc_id) for doc_id in request.doc_ids if int(doc_id) > 0})
    if not doc_ids:
        raise HTTPException(status_code=400, detail="No valid doc_ids provided")
    doc_ids_json = json.dumps(doc_ids)

    existing = (
        db.query(WritebackJob)
        .filter(WritebackJob.status.in_(["pending", "running"]), WritebackJob.doc_ids_json == doc_ids_json)
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

    job = WritebackJob(
        status="pending",
        dry_run=True,
        docs_selected=len(doc_ids),
        docs_changed=docs_changed,
        calls_count=len(calls),
        doc_ids_json=doc_ids_json,
        calls_json=json.dumps([call.model_dump() for call in calls]),
        created_at=_now_iso(),
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

    job = _run_job_execution(settings, db, job, request.dry_run)
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
    query = db.query(WritebackJob).filter(WritebackJob.status == "pending").order_by(WritebackJob.id.asc())
    if limit > 0:
        query = query.limit(limit)
    pending_jobs = query.all()

    completed = 0
    failed = 0
    processed_ids: list[int] = []
    for job in pending_jobs:
        processed_ids.append(int(job.id))
        result = _run_job_execution(settings, db, job, request.dry_run)
        if result.status == "completed":
            completed += 1
        else:
            failed += 1

    return WritebackExecutePendingResponse(
        processed=len(processed_ids),
        completed=completed,
        failed=failed,
        job_ids=processed_ids,
    )
