from __future__ import annotations

import json

from app.api_models import WritebackDryRunItem, WritebackFieldDiff
from app.config import load_settings
from app.models import Document, DocumentPendingTag, Tag
from app.services.writeback.writeback_direct import (
    build_writeback_conflicts,
    execute_direct_selection,
    resolve_direct_selection,
    sync_local_field_from_paperless,
)
from app.services.writeback.writeback_selection import LocalWritebackSelection


def _item(changed_fields: list[str]) -> WritebackDryRunItem:
    return WritebackDryRunItem(
        doc_id=1101,
        changed=bool(changed_fields),
        changed_fields=changed_fields,
        title=WritebackFieldDiff(field="title", original="remote", proposed="local", changed="title" in changed_fields),
        document_date=WritebackFieldDiff(field="issue_date", original="2026-01-01", proposed="2026-02-01", changed="issue_date" in changed_fields),
        correspondent=WritebackFieldDiff(
            field="correspondent",
            original={"id": 1},
            proposed={"id": 2, "pending_name": "Pending"},
            changed="correspondent" in changed_fields,
        ),
        tags=WritebackFieldDiff(
            field="tags",
            original={"ids": [1]},
            proposed={"ids": [2], "pending_names": ["T"]},
            changed="tags" in changed_fields,
        ),
        note=WritebackFieldDiff(
            field="note",
            original={"id": 5, "text": "old"},
            proposed={"id": -1, "text": "new", "action": "replace"},
            changed="note" in changed_fields,
        ),
    )


def test_build_writeback_conflicts_returns_changed_fields():
    conflicts = build_writeback_conflicts(_item(["title", "tags"]))
    fields = [conf.field for conf in conflicts]
    assert fields == ["title", "tags"]


def test_resolve_direct_selection_honors_skip_use_paperless_use_local(session_factory):
    with session_factory() as db:
        local_doc = Document(id=1101, title="Local")
        db.add(local_doc)
        db.commit()

        synced: list[str] = []

        def _sync(_db, _local_doc, _remote_doc, field):
            synced.append(field)

        selection = resolve_direct_selection(
            db=db,
            local_doc=local_doc,
            remote_doc={"title": "Remote"},
            item=_item(["title", "tags", "note"]),
            resolutions={"title": "use_paperless", "tags": "skip", "note": "use_local"},
            needs_conflict_resolution=True,
            sync_local_field_from_paperless_fn=_sync,
        )
        assert synced == ["title"]
        assert selection.apply_local_note is True
        assert selection.patch_payload == {}


def test_execute_direct_selection_emits_calls_and_cleanup():
    calls_executed: list[tuple[str, str]] = []
    cleaned: list[int] = []

    def _execute(_settings, _db, call):
        calls_executed.append((call.method, call.path))

    def _cleanup(_db, doc_id, _payload):
        cleaned.append(doc_id)

    selection = LocalWritebackSelection(
        patch_payload={"title": "X"},
        apply_local_note=True,
        note_original_id=12,
        note_new_text="New",
        note_action="replace",
    )
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False})
    with Session(engine) as db:
        result = execute_direct_selection(
            settings=load_settings(),
            db=db,
            doc_id=1101,
            selection=selection,
            execute_call_fn=_execute,
            cleanup_pending_rows_after_patch_fn=_cleanup,
        )
    assert len(result) == 3
    assert calls_executed[0][0] == "PATCH"
    assert calls_executed[1][0] == "DELETE"
    assert calls_executed[2][0] == "POST"
    assert cleaned == [1101]


def test_sync_local_field_from_paperless_tags_clears_pending(session_factory):
    with session_factory() as db:
        tag = Tag(id=2202, name="RemoteTag")
        doc = Document(id=1102, title="Doc 1102")
        db.add(tag)
        db.add(doc)
        db.add(
            DocumentPendingTag(
                doc_id=1102,
                names_json=json.dumps(["Pending"], ensure_ascii=False),
                updated_at="2026-02-20T10:00:00+00:00",
            )
        )
        db.commit()

        sync_local_field_from_paperless(
            db,
            doc,
            {"tags": [2202]},
            "tags",
            extract_ai_summary_note=lambda _notes: (None, None),
        )
        db.commit()

        assert [t.id for t in doc.tags] == [2202]
        pending = db.query(DocumentPendingTag).filter(DocumentPendingTag.doc_id == 1102).one_or_none()
        assert pending is None
