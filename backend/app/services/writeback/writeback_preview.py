from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.api_models import WritebackDryRunItem, WritebackFieldDiff
from app.models import (
    Correspondent,
    Document,
    DocumentPendingCorrespondent,
    DocumentPendingTag,
    SuggestionAudit,
    Tag,
)
from app.services.integrations import paperless
from app.services.runtime.string_list_json import parse_string_list_json
from app.services.writeback.writeback_plan import compare_document_fields, extract_ai_summary_note

if TYPE_CHECKING:
    from app.config import Settings


def metadata_maps(db: Session) -> tuple[dict[int, str], dict[int, str]]:
    correspondents_by_id = {
        int(corr_id): str(name or "")
        for corr_id, name in db.query(Correspondent.id, Correspondent.name).all()
    }
    tags_by_id = {
        int(tag_id): str(name or "")
        for tag_id, name in db.query(Tag.id, Tag.name).all()
    }
    return correspondents_by_id, tags_by_id


def build_writeback_item(
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


def preview_for_doc_ids(
    settings: Settings,
    db: Session,
    doc_ids: list[int],
) -> list[WritebackDryRunItem]:
    if not doc_ids:
        return []
    local_docs = (
        db.query(Document)
        .options(selectinload(Document.tags), selectinload(Document.notes))
        .filter(Document.id.in_(doc_ids))
        .all()
    )
    local_by_id = {doc.id: doc for doc in local_docs}
    if not local_by_id:
        return []

    correspondents_by_id, tags_by_id = metadata_maps(db)
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
            build_writeback_item(
                local_doc=local_doc,
                remote_doc=remote_doc,
                correspondents_by_id=correspondents_by_id,
                tags_by_id=tags_by_id,
                pending_tag_names=pending_by_doc.get(int(doc_id), []),
                pending_correspondent_name=pending_correspondent_by_doc.get(int(doc_id), ""),
            )
        )
    return items


def local_writeback_candidate_doc_ids(db: Session) -> list[int]:
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

    pending_rows = db.query(DocumentPendingTag.doc_id).yield_per(500)
    for pending_row in pending_rows:
        doc_id = int(pending_row.doc_id)
        if doc_id <= 0 or doc_id in seen:
            continue
        ordered_ids.append(doc_id)
        seen.add(doc_id)
    pending_correspondent_rows = db.query(DocumentPendingCorrespondent.doc_id).yield_per(500)
    for pending_correspondent_row in pending_correspondent_rows:
        doc_id = int(pending_correspondent_row.doc_id)
        if doc_id <= 0 or doc_id in seen:
            continue
        ordered_ids.append(doc_id)
        seen.add(doc_id)
    return ordered_ids
