from __future__ import annotations

from app.api_models import WritebackDryRunItem, WritebackFieldDiff
from app.services.writeback.writeback_selection import build_calls_for_item, collect_local_selection


def _item(changed_fields: list[str]) -> WritebackDryRunItem:
    return WritebackDryRunItem(
        doc_id=1001,
        changed=bool(changed_fields),
        changed_fields=changed_fields,
        title=WritebackFieldDiff(field="title", original="remote", proposed="local", changed="title" in changed_fields),
        document_date=WritebackFieldDiff(field="issue_date", original="2026-01-01", proposed="2026-02-01", changed="issue_date" in changed_fields),
        correspondent=WritebackFieldDiff(
            field="correspondent",
            original={"id": 1, "name": "Old"},
            proposed={"id": 2, "name": "New", "pending_name": "Pending"},
            changed="correspondent" in changed_fields,
        ),
        tags=WritebackFieldDiff(
            field="tags",
            original={"ids": [1], "names": ["A"]},
            proposed={"ids": [2], "names": ["B"], "pending_names": ["C"]},
            changed="tags" in changed_fields,
        ),
        note=WritebackFieldDiff(
            field="note",
            original={"id": 5, "text": "old"},
            proposed={"id": -1, "text": "new", "action": "replace"},
            changed="note" in changed_fields,
        ),
    )


def test_collect_local_selection_normalizes_and_maps_payload():
    selection = collect_local_selection(item=_item(["document_date", "correspondent", "tags"]), fields=["document_date", "correspondent", "tags"])
    assert selection.patch_payload["created"] == "2026-02-01"
    assert selection.patch_payload["correspondent"] == 2
    assert selection.patch_payload["pending_correspondent_name"] == "Pending"
    assert selection.patch_payload["tags"] == [2]
    assert selection.patch_payload["pending_tag_names"] == ["C"]
    assert selection.apply_local_note is False


def test_build_calls_for_item_includes_patch_delete_post_for_note_replace():
    calls = build_calls_for_item(_item(["title", "note"]))
    assert len(calls) == 3
    assert calls[0].method == "PATCH"
    assert calls[0].payload.get("title") == "local"
    assert calls[1].method == "DELETE"
    assert "?id=5" in calls[1].path
    assert calls[2].method == "POST"
    assert calls[2].payload.get("note") == "new"


def test_build_calls_for_item_empty_when_not_changed():
    calls = build_calls_for_item(_item([]))
    assert calls == []
