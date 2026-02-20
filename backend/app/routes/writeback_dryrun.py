from __future__ import annotations

import logging
import json
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session, joinedload

from app.api_models import (
    WritebackHistoryResponse,
    WritebackDryRunCall,
    WritebackDryRunExecuteRequest,
    WritebackDryRunExecuteResponse,
    WritebackExecuteNowRequest,
    WritebackExecuteNowResponse,
    WritebackDirectExecuteRequest,
    WritebackDirectExecuteResponse,
    WritebackJobCreateRequest,
    WritebackJobDetail,
    WritebackExecutePendingRequest,
    WritebackExecutePendingResponse,
    WritebackExecutePendingJobResult,
    WritebackJobExecuteRequest,
    WritebackJobListResponse,
    WritebackJobDeleteResponse,
    WritebackJobSummary,
    WritebackDryRunPreviewResponse,
)
from app.config import Settings
from app.db import get_db
from app.deps import get_settings
from app.models import (
    Correspondent,
    Document,
    DocumentPendingCorrespondent,
    DocumentPendingTag,
    SuggestionAudit,
    Tag,
    WritebackJob,
)
from app.services import paperless
from app.services.json_utils import parse_json_list
from app.services.string_list_json import parse_string_list_json
from app.services.time_utils import utc_now_iso
from app.services.writeback_execution import collect_changed_calls, execute_calls_with_audit, run_writeback_job_execution
from app.services.writeback_plan import extract_ai_summary_note
from app.services.writeback_selection import build_calls_for_item as _build_calls_for_item
from app.services.writeback_direct import (
    build_writeback_conflicts as _build_writeback_conflicts,
    execute_direct_selection as _execute_direct_selection,
    resolve_direct_selection as _resolve_direct_selection,
    sync_local_field_from_paperless as _sync_local_field_from_paperless,
)
from app.services.writeback_preview import (
    build_writeback_item as _build_item,
    local_writeback_candidate_doc_ids as _local_writeback_candidate_doc_ids,
    metadata_maps as _metadata_maps,
    preview_for_doc_ids as _preview_for_doc_ids,
)

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

def _cleanup_pending_rows_after_patch(db: Session, doc_id: int, patch_payload: dict[str, Any]) -> None:
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
        except Exception:
            continue
    return doc_ids


def _deserialize_calls(job: WritebackJob) -> list[WritebackDryRunCall]:
    calls: list[WritebackDryRunCall] = []
    for item in parse_json_list(job.calls_json):
        if not isinstance(item, dict):
            continue
        try:
            calls.append(WritebackDryRunCall(**item))
        except Exception:
            continue
    return calls


def _job_detail(job: WritebackJob) -> WritebackJobDetail:
    return WritebackJobDetail(
        **_job_summary(job).model_dump(),
        doc_ids=_deserialize_doc_ids(job),
        calls=_deserialize_calls(job),
    )


def _resolve_paperless_tag_ids(
    settings: Settings,
    db: Session,
    local_tag_ids: list[int],
    pending_tag_names: list[str] | None = None,
) -> list[int]:
    local_tags = db.query(Tag).filter(Tag.id.in_(local_tag_ids)).all()
    local_names = [str(tag.name or "").strip() for tag in local_tags if str(tag.name or "").strip()]
    for name in (pending_tag_names or []):
        clean = str(name or "").strip()
        if clean and clean not in local_names:
            local_names.append(clean)
    if not local_names:
        return []
    remote_tags = paperless.list_all_tags(settings)
    remote_by_name = {
        str(tag.get("name") or "").strip().lower(): int(tag.get("id"))
        for tag in remote_tags
        if isinstance(tag.get("id"), int) and str(tag.get("name") or "").strip()
    }
    resolved_ids: list[int] = []
    for name in local_names:
        key = name.lower()
        existing_id = remote_by_name.get(key)
        if existing_id is None:
            created = paperless.create_tag(settings, name)
            created_id = created.get("id")
            if isinstance(created_id, int):
                existing_id = created_id
                remote_by_name[key] = created_id
        if isinstance(existing_id, int):
            resolved_ids.append(existing_id)
            local_tag = db.query(Tag).filter(Tag.id == existing_id).one_or_none()
            if not local_tag:
                db.add(Tag(id=existing_id, name=name))
            elif (local_tag.name or "").strip() != name:
                local_tag.name = name
    return sorted(set(resolved_ids))


def _resolve_paperless_correspondent_id(
    settings: Settings,
    db: Session,
    local_correspondent_id: int | None,
    pending_correspondent_name: str | None = None,
) -> int | None:
    def _as_int(value: Any) -> int | None:
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return None
            try:
                return int(raw)
            except Exception:
                return None
        return None

    def _migrate_local_references(old_id: int | None, new_id: int, name: str) -> None:
        local_corr = db.query(Correspondent).filter(Correspondent.id == int(new_id)).one_or_none()
        if not local_corr:
            db.add(Correspondent(id=int(new_id), name=name))
            # Ensure FK target row exists before remapping document references.
            db.flush()
        elif (local_corr.name or "").strip() != name:
            local_corr.name = name
            db.flush()
        if old_id and old_id != new_id:
            db.query(Document).filter(Document.correspondent_id == int(old_id)).update(
                {"correspondent_id": int(new_id)},
                synchronize_session=False,
            )

    local_name = str(pending_correspondent_name or "").strip()
    local_id = int(local_correspondent_id) if isinstance(local_correspondent_id, int) and local_correspondent_id > 0 else None
    if not local_name and local_id:
        local_row = db.query(Correspondent).filter(Correspondent.id == int(local_id)).one_or_none()
        local_name = str(local_row.name or "").strip() if local_row else ""

    remote_rows = paperless.list_all_correspondents(settings)
    remote_by_id = {
        int(row.get("id")): str(row.get("name") or "").strip()
        for row in remote_rows
        if _as_int(row.get("id")) is not None
    }
    if local_id and local_id in remote_by_id:
        return local_id

    remote_by_name = {
        str(row.get("name") or "").strip().lower(): _as_int(row.get("id"))
        for row in remote_rows
        if _as_int(row.get("id")) is not None and str(row.get("name") or "").strip()
    }
    if not local_name:
        return None
    existing_id = remote_by_name.get(local_name.lower())
    if existing_id is None:
        created = paperless.create_correspondent(settings, local_name)
        created_id = _as_int(created.get("id"))
        if created_id is not None:
            existing_id = created_id

    if isinstance(existing_id, int):
        _migrate_local_references(local_id, int(existing_id), local_name)
        return existing_id
    return None


def _execute_call(settings: Settings, db: Session, call: WritebackDryRunCall) -> None:
    method = call.method.upper()
    if method == "PATCH":
        payload = dict(call.payload or {})
        had_tags = False
        had_correspondent = False
        resolved_correspondent_id: int | None = None
        raw_correspondent = payload.get("correspondent")
        pending_correspondent_name = payload.pop("pending_correspondent_name", None)
        if "correspondent" in payload:
            had_correspondent = True
            local_correspondent_id = int(raw_correspondent) if isinstance(raw_correspondent, int) else None
            resolved_correspondent_id = _resolve_paperless_correspondent_id(
                settings,
                db,
                local_correspondent_id,
                str(pending_correspondent_name or "").strip() or None,
            )
            if resolved_correspondent_id is None and str(pending_correspondent_name or "").strip():
                raise RuntimeError(
                    f"Unable to resolve/create correspondent: {str(pending_correspondent_name).strip()}"
                )
            if resolved_correspondent_id is None:
                payload.pop("correspondent", None)
            else:
                payload["correspondent"] = resolved_correspondent_id
        raw_tags = payload.get("tags")
        if isinstance(raw_tags, list):
            had_tags = True
            local_tag_ids = [int(tag_id) for tag_id in raw_tags if isinstance(tag_id, int)]
            pending_names_raw = payload.pop("pending_tag_names", [])
            pending_names = [str(name).strip() for name in pending_names_raw if str(name).strip()] if isinstance(pending_names_raw, list) else []
            payload["tags"] = _resolve_paperless_tag_ids(settings, db, local_tag_ids, pending_names)
            db.flush()
        if payload.get("created") in (None, ""):
            payload.pop("created", None)
        if payload.get("title") is None:
            payload.pop("title", None)
        if not payload:
            return
        try:
            paperless.update_document(settings, int(call.doc_id), payload)
        except httpx.HTTPStatusError as exc:
            response_text = ""
            try:
                response_text = str(exc.response.text or "").strip()
            except Exception:
                response_text = ""
            status_code = int(exc.response.status_code) if exc.response is not None else 0
            # Paperless often rejects null/invalid created fields; retry once without created.
            if status_code == 400 and "created" in payload:
                retry_payload = dict(payload)
                retry_payload.pop("created", None)
                if retry_payload:
                    try:
                        paperless.update_document(settings, int(call.doc_id), retry_payload)
                        payload = retry_payload
                    except httpx.HTTPStatusError as retry_exc:
                        retry_text = ""
                        try:
                            retry_text = str(retry_exc.response.text or "").strip()
                        except Exception:
                            retry_text = ""
                        raise RuntimeError(
                            f"Paperless PATCH failed doc={int(call.doc_id)} status={int(retry_exc.response.status_code)} "
                            f"payload={retry_payload} response={retry_text[:500]}"
                        ) from retry_exc
                else:
                    raise RuntimeError(
                        f"Paperless PATCH failed doc={int(call.doc_id)} status={status_code} "
                        f"payload={payload} response={response_text[:500]}"
                    ) from exc
            else:
                raise RuntimeError(
                    f"Paperless PATCH failed doc={int(call.doc_id)} status={status_code} "
                    f"payload={payload} response={response_text[:500]}"
                ) from exc
        if had_tags:
            local_doc = (
                db.query(Document)
                .options(joinedload(Document.tags))
                .filter(Document.id == int(call.doc_id))
                .one_or_none()
            )
            if local_doc:
                resolved_ids_raw = payload.get("tags")
                resolved_ids: list[object] = resolved_ids_raw if isinstance(resolved_ids_raw, list) else []
                resolved_ids_int: list[int] = [tag_id for tag_id in resolved_ids if isinstance(tag_id, int)]
                existing_tags = db.query(Tag).filter(Tag.id.in_(resolved_ids_int)).all() if resolved_ids_int else []
                by_id = {tag.id: tag for tag in existing_tags}
                local_doc.tags = [by_id[tag_id] for tag_id in resolved_ids_int if tag_id in by_id]
        if had_correspondent:
            local_doc = db.query(Document).filter(Document.id == int(call.doc_id)).one_or_none()
            if local_doc:
                local_doc.correspondent_id = resolved_correspondent_id
            pending_corr_row = (
                db.query(DocumentPendingCorrespondent)
                .filter(DocumentPendingCorrespondent.doc_id == int(call.doc_id))
                .one_or_none()
            )
            if pending_corr_row:
                db.delete(pending_corr_row)
        return
    if method == "POST":
        payload = dict(call.payload or {})
        note = str(payload.get("note") or "")
        paperless.add_document_note(settings, int(call.doc_id), note)
        return
    if method == "DELETE":
        path = str(call.path or "")
        note_id: int | None = None
        parsed = urlsplit(path)
        query_id = parse_qs(parsed.query).get("id")
        if query_id and query_id[0]:
            try:
                note_id = int(query_id[0])
            except Exception:
                note_id = None
        if note_id is None:
            try:
                segment = parsed.path.rstrip("/").split("/")[-1]
                note_id = int(segment)
            except Exception:
                note_id = None
        if note_id is None:
            raise RuntimeError(f"Cannot parse note id from path: {path}")
        paperless.delete_document_note(settings, int(call.doc_id), note_id)
        return
    raise RuntimeError(f"Unsupported writeback method: {method}")


def _reviewed_timestamp_for_doc(settings: Settings, db: Session, doc_id: int) -> str:
    try:
        remote_doc = paperless.get_document(settings, int(doc_id))
        modified = str(remote_doc.get("modified") or "").strip()
        if modified:
            local_doc = db.get(Document, int(doc_id))
            if local_doc:
                local_doc.modified = modified
            return modified
    except Exception:
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
        .options(joinedload(Document.tags), joinedload(Document.notes))
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
    pending_correspondent_name = str(pending_correspondent_row.name or "").strip() if pending_correspondent_row else ""
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
    needs_conflict_resolution = bool(known_modified and current_modified and known_modified != current_modified)
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
        raise HTTPException(status_code=400, detail=str(exc))

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
    query = db.query(WritebackJob).filter(WritebackJob.status == "pending").order_by(WritebackJob.id.asc())
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
