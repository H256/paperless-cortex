from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from app.api_models import WritebackConflictField, WritebackDryRunCall, WritebackDryRunItem, WritebackFieldDiff
from app.config import Settings
from app.models import Document, DocumentNote, DocumentPendingCorrespondent, DocumentPendingTag
from app.services.documents.note_ids import next_local_note_id
from app.services.runtime.time_utils import utc_now_iso
from app.services.writeback.writeback_selection import LocalWritebackSelection, collect_local_selection, normalize_changed_field


def item_field_by_name(item: WritebackDryRunItem, field: str) -> WritebackFieldDiff | None:
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


def sync_local_field_from_paperless(
    db: Session,
    local_doc: Document,
    remote_doc: dict[str, Any],
    field: str,
    *,
    extract_ai_summary_note: Callable[[list[dict[str, Any]]], tuple[int | None, str | None]],
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
        remote_tags_raw = remote_doc.get("tags")
        remote_tags: list[object] = remote_tags_raw if isinstance(remote_tags_raw, list) else []
        local_doc.tags = []
        for tag_id in remote_tags:
            if not isinstance(tag_id, int):
                continue
            # Tags are synced in metadata; only assign ids that already exist locally.
            from app.models import Tag

            tag_row = db.query(Tag).filter(Tag.id == int(tag_id)).one_or_none()
            if tag_row:
                local_doc.tags.append(tag_row)
        pending_row = (
            db.query(DocumentPendingTag)
            .filter(DocumentPendingTag.doc_id == int(local_doc.id))
            .one_or_none()
        )
        if pending_row:
            db.delete(pending_row)
        return
    if field == "note":
        notes_raw = remote_doc.get("notes")
        notes: list[dict[str, Any]] = notes_raw if isinstance(notes_raw, list) else []
        remote_note_id, remote_note_text = extract_ai_summary_note(
            notes
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
                    created=utc_now_iso(),
                )
            )


def build_writeback_conflicts(item: WritebackDryRunItem) -> list[WritebackConflictField]:
    conflicts: list[WritebackConflictField] = []
    for field in item.changed_fields:
        diff = item_field_by_name(item, field)
        if diff is None:
            continue
        conflicts.append(
            WritebackConflictField(
                field=field,
                paperless=diff.original,
                local=diff.proposed,
            )
        )
    return conflicts


def resolve_direct_selection(
    *,
    db: Session,
    local_doc: Document,
    remote_doc: dict[str, Any],
    item: WritebackDryRunItem,
    resolutions: dict[str, str],
    needs_conflict_resolution: bool,
    sync_local_field_from_paperless_fn: Callable[[Session, Document, dict[str, Any], str], None],
) -> LocalWritebackSelection:
    local_fields: list[str] = []
    for field in item.changed_fields:
        normalized_field = normalize_changed_field(field)
        action = resolutions.get(normalized_field)
        if action not in {"skip", "use_paperless", "use_local"}:
            action = "use_local" if not needs_conflict_resolution else "skip"
        if action == "skip":
            continue
        if action == "use_paperless":
            sync_local_field_from_paperless_fn(db, local_doc, remote_doc, normalized_field)
            continue
        local_fields.append(normalized_field)
    return collect_local_selection(item=item, fields=local_fields)


def execute_direct_selection(
    *,
    settings: Settings,
    db: Session,
    doc_id: int,
    selection: LocalWritebackSelection,
    execute_call_fn: Callable[[Settings, Session, WritebackDryRunCall], None],
    cleanup_pending_rows_after_patch_fn: Callable[[Session, int, dict[str, Any]], None],
) -> list[WritebackDryRunCall]:
    calls: list[WritebackDryRunCall] = []
    if selection.patch_payload:
        patch_call = WritebackDryRunCall(
            doc_id=doc_id,
            method="PATCH",
            path=f"/api/documents/{doc_id}/",
            payload=selection.patch_payload,
        )
        execute_call_fn(settings, db, patch_call)
        calls.append(patch_call)
        cleanup_pending_rows_after_patch_fn(db, doc_id, selection.patch_payload)
    if selection.apply_local_note and selection.note_action == "replace" and selection.note_original_id:
        del_call = WritebackDryRunCall(
            doc_id=doc_id,
            method="DELETE",
            path=f"/api/documents/{doc_id}/notes/?id={selection.note_original_id}",
            payload={},
        )
        execute_call_fn(settings, db, del_call)
        calls.append(del_call)
    if selection.apply_local_note and selection.note_new_text:
        add_call = WritebackDryRunCall(
            doc_id=doc_id,
            method="POST",
            path=f"/api/documents/{doc_id}/notes/",
            payload={"note": selection.note_new_text},
        )
        execute_call_fn(settings, db, add_call)
        calls.append(add_call)
    return calls
