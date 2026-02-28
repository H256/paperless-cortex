from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.api_models import WritebackDryRunCall, WritebackDryRunItem


@dataclass
class LocalWritebackSelection:
    patch_payload: dict[str, Any]
    apply_local_note: bool
    note_original_id: int | None
    note_new_text: str | None
    note_action: str


def normalize_changed_field(field: str) -> str:
    return "issue_date" if field in {"document_date", "issue_date"} else field


def collect_local_selection(*, item: WritebackDryRunItem, fields: list[str]) -> LocalWritebackSelection:
    patch_payload: dict[str, Any] = {}
    apply_local_note = False
    note_original_id: int | None = None
    note_new_text: str | None = None
    note_action = ""
    for field in fields:
        normalized_field = normalize_changed_field(field)
        if normalized_field == "title":
            patch_payload["title"] = item.title.proposed
            continue
        if normalized_field == "issue_date":
            patch_payload["created"] = item.document_date.proposed
            continue
        if normalized_field == "correspondent" and isinstance(item.correspondent.proposed, dict):
            patch_payload["correspondent"] = item.correspondent.proposed.get("id")
            patch_payload["pending_correspondent_name"] = item.correspondent.proposed.get("pending_name")
            continue
        if normalized_field == "tags" and isinstance(item.tags.proposed, dict):
            patch_payload["tags"] = item.tags.proposed.get("ids") or []
            patch_payload["pending_tag_names"] = item.tags.proposed.get("pending_names") or []
            continue
        if normalized_field == "note" and isinstance(item.note.proposed, dict):
            apply_local_note = True
            original = item.note.original if isinstance(item.note.original, dict) else {}
            note_original_id = int(original["id"]) if isinstance(original.get("id"), int) else None
            note_new_text = str(item.note.proposed.get("text") or "").strip() or None
            note_action = str(item.note.proposed.get("action") or "")
    return LocalWritebackSelection(
        patch_payload=patch_payload,
        apply_local_note=apply_local_note,
        note_original_id=note_original_id,
        note_new_text=note_new_text,
        note_action=note_action,
    )


def build_calls_for_item(item: WritebackDryRunItem) -> list[WritebackDryRunCall]:
    calls: list[WritebackDryRunCall] = []
    if not item.changed:
        return calls

    selection = collect_local_selection(item=item, fields=item.changed_fields)
    if selection.patch_payload:
        calls.append(
            WritebackDryRunCall(
                doc_id=item.doc_id,
                method="PATCH",
                path=f"/api/documents/{item.doc_id}/",
                payload=selection.patch_payload,
            )
        )

    if selection.apply_local_note and selection.note_new_text:
        if selection.note_action == "replace" and selection.note_original_id:
            calls.append(
                WritebackDryRunCall(
                    doc_id=item.doc_id,
                    method="DELETE",
                    path=f"/api/documents/{item.doc_id}/notes/?id={int(selection.note_original_id)}",
                    payload={},
                )
            )
        calls.append(
            WritebackDryRunCall(
                doc_id=item.doc_id,
                method="POST",
                path=f"/api/documents/{item.doc_id}/notes/",
                payload={"note": selection.note_new_text},
            )
        )
    return calls
