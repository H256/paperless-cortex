from __future__ import annotations

from datetime import datetime, timezone
import logging
import json
from typing import Any
from urllib.parse import parse_qs, urlsplit

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
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
    WritebackConflictField,
    WritebackJobCreateRequest,
    WritebackJobDetail,
    WritebackExecutePendingRequest,
    WritebackExecutePendingResponse,
    WritebackExecutePendingJobResult,
    WritebackJobExecuteRequest,
    WritebackJobListResponse,
    WritebackJobDeleteResponse,
    WritebackJobSummary,
    WritebackDryRunItem,
    WritebackDryRunPreviewResponse,
    WritebackFieldDiff,
)
from app.config import Settings
from app.db import get_db
from app.deps import get_settings
from app.models import (
    Correspondent,
    Document,
    DocumentNote,
    DocumentPendingCorrespondent,
    DocumentPendingTag,
    SuggestionAudit,
    Tag,
    WritebackJob,
)
from app.services import paperless
from app.services.json_utils import parse_json_list
from app.services.note_ids import next_local_note_id
from app.services.string_list_json import parse_string_list_json
from app.services.writeback_plan import compare_document_fields, extract_ai_summary_note

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/writeback", tags=["writeback"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _metadata_maps(db: Session) -> tuple[dict[int, str], dict[int, str]]:
    correspondents_by_id = {
        int(corr_id): str(name or "")
        for corr_id, name in db.query(Correspondent.id, Correspondent.name).all()
    }
    tags_by_id = {
        int(tag_id): str(name or "")
        for tag_id, name in db.query(Tag.id, Tag.name).all()
    }
    return correspondents_by_id, tags_by_id


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
    pending_tag_names: list[str] | None = None,
    pending_correspondent_name: str | None = None,
) -> WritebackDryRunItem:
    local_issue_date = local_doc.document_date or local_doc.created
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
        local_date=local_issue_date,
        remote_date=remote_doc.get("created"),
        local_correspondent_id=local_doc.correspondent_id,
        remote_correspondent_id=remote_doc.get("correspondent"),
        local_pending_correspondent_name=pending_correspondent_name,
        local_tags=local_tags,
        remote_tags=remote_tags,
        local_pending_tag_names=pending_tag_names or [],
        local_ai_note=local_note_text,
        remote_ai_note=remote_note_text,
    )

    remote_correspondent_id = remote_doc.get("correspondent")
    local_corr_name = (
        correspondents_by_id.get(local_doc.correspondent_id or 0)
        if local_doc.correspondent_id
        else (str(pending_correspondent_name or "").strip() or None)
    )
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
            field="issue_date",
            original=remote_doc.get("created"),
            proposed=local_issue_date,
            changed="issue_date" in changed_fields,
        ),
        correspondent=WritebackFieldDiff(
            field="correspondent",
            original={"id": remote_correspondent_id, "name": remote_corr_name},
            proposed={
                "id": local_doc.correspondent_id,
                "name": local_corr_name,
                "pending_name": str(pending_correspondent_name or "").strip() or None,
            },
            changed="correspondent" in changed_fields,
        ),
        tags=WritebackFieldDiff(
            field="tags",
            original={"ids": remote_tags, "names": remote_tag_names},
            proposed={"ids": local_tags, "names": local_tag_names, "pending_names": pending_tag_names or []},
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

    correspondents_by_id, tags_by_id = _metadata_maps(db)
    pending_rows = (
        db.query(DocumentPendingTag)
        .filter(DocumentPendingTag.doc_id.in_(list(local_by_id.keys())))
        .all()
    )
    pending_correspondent_rows = (
        db.query(DocumentPendingCorrespondent.doc_id, DocumentPendingCorrespondent.name)
        .filter(DocumentPendingCorrespondent.doc_id.in_(list(local_by_id.keys())))
        .all()
    )
    pending_by_doc: dict[int, list[str]] = {}
    for row in pending_rows:
        pending_by_doc[int(row.doc_id)] = parse_string_list_json(row.names_json)
    pending_correspondent_by_doc: dict[int, str] = {
        int(row.doc_id): str(row.name or "").strip()
        for row in pending_correspondent_rows
        if str(row.name or "").strip()
    }

    remote_docs = paperless.get_documents_cached(settings, list(local_by_id.keys()))
    items: list[WritebackDryRunItem] = []
    for doc_id in doc_ids:
        local_doc = local_by_id.get(doc_id)
        if not local_doc:
            continue
        remote_doc = remote_docs.get(int(doc_id))
        if not remote_doc:
            remote_doc = paperless.get_document_cached(settings, doc_id)
        items.append(
            _build_item(
                local_doc=local_doc,
                remote_doc=remote_doc,
                correspondents_by_id=correspondents_by_id,
                tags_by_id=tags_by_id,
                pending_tag_names=pending_by_doc.get(int(doc_id), []),
                pending_correspondent_name=pending_correspondent_by_doc.get(int(doc_id), ""),
            )
        )
    return items


def _local_writeback_candidate_doc_ids(db: Session) -> list[int]:
    audit_rows = (
        db.query(
            SuggestionAudit.doc_id,
            func.max(SuggestionAudit.created_at).label("last_applied_at"),
        )
        .filter(SuggestionAudit.action.like("apply_to_document:%"))
        .group_by(SuggestionAudit.doc_id)
        .order_by(func.max(SuggestionAudit.created_at).desc().nullslast())
        .all()
    )
    ordered_ids: list[int] = []
    seen: set[int] = set()
    for row in audit_rows:
        doc_id = int(row.doc_id)
        if doc_id <= 0 or doc_id in seen:
            continue
        ordered_ids.append(doc_id)
        seen.add(doc_id)

    pending_rows = db.query(DocumentPendingTag.doc_id).all()
    for row in pending_rows:
        doc_id = int(row.doc_id)
        if doc_id <= 0 or doc_id in seen:
            continue
        ordered_ids.append(doc_id)
        seen.add(doc_id)
    pending_correspondent_rows = db.query(DocumentPendingCorrespondent.doc_id).all()
    for row in pending_correspondent_rows:
        doc_id = int(row.doc_id)
        if doc_id <= 0 or doc_id in seen:
            continue
        ordered_ids.append(doc_id)
        seen.add(doc_id)
    return ordered_ids


def _build_calls_for_item(item: WritebackDryRunItem) -> list[WritebackDryRunCall]:
    calls: list[WritebackDryRunCall] = []
    if not item.changed:
        return calls

    payload: dict[str, Any] = {}
    if item.title.changed:
        payload["title"] = item.title.proposed
    if item.document_date.changed:
        payload["created"] = item.document_date.proposed
    if item.correspondent.changed and isinstance(item.correspondent.proposed, dict):
        payload["correspondent"] = item.correspondent.proposed.get("id")
        payload["pending_correspondent_name"] = item.correspondent.proposed.get("pending_name")
    if item.tags.changed and isinstance(item.tags.proposed, dict):
        payload["tags"] = item.tags.proposed.get("ids") or []
        payload["pending_tag_names"] = item.tags.proposed.get("pending_names") or []
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
                    path=f"/api/documents/{item.doc_id}/notes/?id={int(original_note_id)}",
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

    if isinstance(local_correspondent_id, int) and local_correspondent_id > 0:
        return int(local_correspondent_id)

    local_name = str(pending_correspondent_name or "").strip()
    if not local_name and isinstance(local_correspondent_id, int):
        local_row = db.query(Correspondent).filter(Correspondent.id == int(local_correspondent_id)).one_or_none()
        local_name = str(local_row.name or "").strip() if local_row else ""
    if not local_name:
        return None

    remote_rows = paperless.list_all_correspondents(settings)
    remote_by_name = {
        str(row.get("name") or "").strip().lower(): _as_int(row.get("id"))
        for row in remote_rows
        if _as_int(row.get("id")) is not None and str(row.get("name") or "").strip()
    }
    existing_id = remote_by_name.get(local_name.lower())
    if existing_id is None:
        created = paperless.create_correspondent(settings, local_name)
        created_id = _as_int(created.get("id"))
        if created_id is not None:
            existing_id = created_id

    if isinstance(existing_id, int):
        local_corr = db.query(Correspondent).filter(Correspondent.id == existing_id).one_or_none()
        if not local_corr:
            db.add(Correspondent(id=existing_id, name=local_name))
        elif (local_corr.name or "").strip() != local_name:
            local_corr.name = local_name
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
        paperless.update_document(settings, int(call.doc_id), payload)
        if had_tags:
            local_doc = (
                db.query(Document)
                .options(joinedload(Document.tags))
                .filter(Document.id == int(call.doc_id))
                .one_or_none()
            )
            if local_doc:
                resolved_ids = payload.get("tags") if isinstance(payload.get("tags"), list) else []
                resolved_ids_int = [int(tag_id) for tag_id in resolved_ids if isinstance(tag_id, int)]
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
    return _now_iso()


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
    executed_doc_ids: set[int] = set()
    try:
        for call in calls:
            executed_doc_ids.add(int(call.doc_id))
            logger.info(
                "WRITEBACK %s doc=%s method=%s path=%s payload=%s",
                "DRY-RUN" if dry_run else "EXECUTE",
                call.doc_id,
                call.method,
                call.path,
                call.payload,
            )
            if not dry_run:
                _execute_call(settings, db, call)
                if call.method.upper() == "PATCH" and isinstance(call.payload, dict) and "tags" in call.payload:
                    pending_row = (
                        db.query(DocumentPendingTag)
                        .filter(DocumentPendingTag.doc_id == int(call.doc_id))
                        .one_or_none()
                    )
                    if pending_row:
                        db.delete(pending_row)
                if call.method.upper() == "PATCH" and isinstance(call.payload, dict) and "correspondent" in call.payload:
                    pending_corr_row = (
                        db.query(DocumentPendingCorrespondent)
                        .filter(DocumentPendingCorrespondent.doc_id == int(call.doc_id))
                        .one_or_none()
                    )
                    if pending_corr_row:
                        db.delete(pending_corr_row)
        if not dry_run and executed_doc_ids:
            for doc_id in sorted(executed_doc_ids):
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


def _item_field_by_name(item: WritebackDryRunItem, field: str) -> WritebackFieldDiff | None:
    if field == "title":
        return item.title
    if field == "issue_date":
        return item.document_date
    if field == "correspondent":
        return item.correspondent
    if field == "tags":
        return item.tags
    if field == "note":
        return item.note
    return None


def _sync_local_field_from_paperless(
    db: Session,
    local_doc: Document,
    remote_doc: dict[str, Any],
    field: str,
) -> None:
    if field == "title":
        local_doc.title = str(remote_doc.get("title") or "").strip() or None
        return
    if field == "issue_date":
        local_doc.document_date = str(remote_doc.get("created") or "").strip() or None
        return
    if field == "correspondent":
        remote_corr = remote_doc.get("correspondent")
        local_doc.correspondent_id = int(remote_corr) if isinstance(remote_corr, int) else None
        pending_corr_row = (
            db.query(DocumentPendingCorrespondent)
            .filter(DocumentPendingCorrespondent.doc_id == int(local_doc.id))
            .one_or_none()
        )
        if pending_corr_row:
            db.delete(pending_corr_row)
        return
    if field == "tags":
        remote_tags_raw = remote_doc.get("tags") or []
        remote_tag_ids = [int(tag_id) for tag_id in remote_tags_raw if isinstance(tag_id, int)]
        if not remote_tag_ids:
            local_doc.tags = []
            return
        existing_tags = db.query(Tag).filter(Tag.id.in_(remote_tag_ids)).all()
        by_id = {tag.id: tag for tag in existing_tags}
        local_doc.tags = [by_id[tag_id] for tag_id in remote_tag_ids if tag_id in by_id]
        pending_row = (
            db.query(DocumentPendingTag)
            .filter(DocumentPendingTag.doc_id == int(local_doc.id))
            .one_or_none()
        )
        if pending_row:
            db.delete(pending_row)
        return
    if field == "note":
        remote_note_id, remote_note_text = extract_ai_summary_note(
            remote_doc.get("notes") if isinstance(remote_doc.get("notes"), list) else []
        )
        ai_local_notes = [note for note in (local_doc.notes or []) if str(note.note or "").strip().endswith("KI-Zusammenfassung")]
        for note in ai_local_notes:
            db.delete(note)
        if remote_note_id and remote_note_text:
            db.add(
                DocumentNote(
                    id=next_local_note_id(db),
                    document_id=local_doc.id,
                    note=remote_note_text,
                    created=_now_iso(),
                )
            )
        return


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
        conflicts: list[WritebackConflictField] = []
        for field in item.changed_fields:
            diff = _item_field_by_name(item, field)
            if diff is None:
                continue
            conflicts.append(
                WritebackConflictField(
                    field=field,
                    paperless=diff.original,
                    local=diff.proposed,
                )
            )
        return WritebackDirectExecuteResponse(
            status="conflicts",
            docs_changed=len(item.changed_fields),
            calls_count=0,
            doc_ids=[],
            calls=[],
            conflicts=conflicts,
        )

    calls: list[WritebackDryRunCall] = []
    patch_payload: dict[str, Any] = {}
    apply_local_note = False
    note_original_id: int | None = None
    note_new_text: str | None = None

    resolutions = {str(k): str(v) for k, v in (request.resolutions or {}).items()}
    for field in item.changed_fields:
        normalized_field = "issue_date" if field in {"document_date", "issue_date"} else field
        action = resolutions.get(normalized_field)
        if action not in {"skip", "use_paperless", "use_local"}:
            action = "use_local" if not needs_conflict_resolution else "skip"
        if action == "skip":
            continue
        if action == "use_paperless":
            _sync_local_field_from_paperless(db, local_doc, remote_doc, normalized_field)
            continue
        if normalized_field == "title":
            patch_payload["title"] = item.title.proposed
        elif normalized_field == "issue_date":
            patch_payload["created"] = item.document_date.proposed
        elif normalized_field == "correspondent" and isinstance(item.correspondent.proposed, dict):
            patch_payload["correspondent"] = item.correspondent.proposed.get("id")
            patch_payload["pending_correspondent_name"] = item.correspondent.proposed.get("pending_name")
        elif normalized_field == "tags" and isinstance(item.tags.proposed, dict):
            patch_payload["tags"] = item.tags.proposed.get("ids") or []
            patch_payload["pending_tag_names"] = item.tags.proposed.get("pending_names") or []
        elif normalized_field == "note" and isinstance(item.note.proposed, dict):
            apply_local_note = True
            original = item.note.original if isinstance(item.note.original, dict) else {}
            note_original_id = int(original["id"]) if isinstance(original.get("id"), int) else None
            note_new_text = str(item.note.proposed.get("text") or "").strip() or None

    if patch_payload:
        call = WritebackDryRunCall(
            doc_id=doc_id,
            method="PATCH",
            path=f"/api/documents/{doc_id}/",
            payload=patch_payload,
        )
        _execute_call(settings, db, call)
        calls.append(call)
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

    if apply_local_note and note_original_id:
        del_call = WritebackDryRunCall(
            doc_id=doc_id,
            method="DELETE",
            path=f"/api/documents/{doc_id}/notes/?id={note_original_id}",
            payload={},
        )
        _execute_call(settings, db, del_call)
        calls.append(del_call)
    if apply_local_note and note_new_text:
        add_call = WritebackDryRunCall(
            doc_id=doc_id,
            method="POST",
            path=f"/api/documents/{doc_id}/notes/",
            payload={"note": note_new_text},
        )
        _execute_call(settings, db, add_call)
        calls.append(add_call)

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
    calls: list[WritebackDryRunCall] = []
    docs_changed = 0
    executed_doc_ids: set[int] = set()
    for item in preview_items:
        if not item.changed:
            continue
        docs_changed += 1
        item_calls = _build_calls_for_item(item)
        calls.extend(item_calls)

    for call in calls:
        logger.info(
            "WRITEBACK EXECUTE-NOW doc=%s method=%s path=%s payload=%s",
            call.doc_id,
            call.method,
            call.path,
            call.payload,
        )
        _execute_call(settings, db, call)
        executed_doc_ids.add(int(call.doc_id))

    if executed_doc_ids:
        for doc_id in sorted(executed_doc_ids):
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

    completed = 0
    failed = 0
    processed_ids: list[int] = []
    processed_doc_ids: set[int] = set()
    job_results: list[WritebackExecutePendingJobResult] = []
    for index, job in enumerate(query.yield_per(50), start=1):
        if limit > 0 and index > limit:
            break
        processed_ids.append(int(job.id))
        result = _run_job_execution(settings, db, job, request.dry_run)
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
