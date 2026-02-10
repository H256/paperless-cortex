from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from app.api_models import (
    WritebackDryRunCall,
    WritebackDryRunExecuteRequest,
    WritebackDryRunExecuteResponse,
    WritebackDryRunItem,
    WritebackDryRunPreviewResponse,
    WritebackFieldDiff,
)
from app.config import Settings
from app.db import get_db
from app.deps import get_settings
from app.models import Correspondent, Document, DocumentNote, Tag
from app.services import paperless
from app.services.writeback_plan import compare_document_fields, extract_ai_summary_note

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/writeback", tags=["writeback"])


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
            call = WritebackDryRunCall(
                doc_id=item.doc_id,
                method="PATCH",
                path=f"/api/documents/{item.doc_id}/",
                payload=payload,
            )
            calls.append(call)
            logger.info(
                "DRY-RUN writeback doc=%s method=%s path=%s payload=%s",
                call.doc_id,
                call.method,
                call.path,
                call.payload,
            )

        if item.note.changed and isinstance(item.note.proposed, dict):
            proposed_text = str(item.note.proposed.get("text") or "")
            action = str(item.note.proposed.get("action") or "")
            original_note = item.note.original if isinstance(item.note.original, dict) else {}
            original_note_id = original_note.get("id")
            if action == "replace" and original_note_id:
                delete_call = WritebackDryRunCall(
                    doc_id=item.doc_id,
                    method="DELETE",
                    path=f"/api/documents/{item.doc_id}/notes/{int(original_note_id)}/",
                    payload={},
                )
                calls.append(delete_call)
                logger.info(
                    "DRY-RUN writeback doc=%s method=%s path=%s",
                    delete_call.doc_id,
                    delete_call.method,
                    delete_call.path,
                )
            add_call = WritebackDryRunCall(
                doc_id=item.doc_id,
                method="POST",
                path=f"/api/documents/{item.doc_id}/notes/",
                payload={"note": proposed_text},
            )
            calls.append(add_call)
            logger.info(
                "DRY-RUN writeback doc=%s method=%s path=%s payload=%s",
                add_call.doc_id,
                add_call.method,
                add_call.path,
                add_call.payload,
            )

    return WritebackDryRunExecuteResponse(
        docs_selected=len(request.doc_ids),
        docs_changed=docs_changed,
        calls=calls,
    )
