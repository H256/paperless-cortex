from __future__ import annotations

from typing import Any

from app.api_models import WritebackDryRunCall
from app.config import load_settings
from app.models import Document, DocumentPendingCorrespondent, Tag
from app.services.writeback.writeback_apply import execute_writeback_call


def test_execute_writeback_call_patch_resolves_metadata_and_updates_local(
    session_factory: Any, monkeypatch: Any
) -> None:
    from app.services.integrations import paperless

    settings = load_settings()
    with session_factory() as db:
        db.add(Tag(id=1, name="Existing"))
        db.add(Document(id=1201, title="Doc 1201", correspondent_id=None))
        db.add(
            DocumentPendingCorrespondent(
                doc_id=1201,
                name="New Corr",
                updated_at="2026-02-20T10:00:00+00:00",
            )
        )
        db.commit()

        monkeypatch.setattr(paperless, "list_all_tags", lambda *_args, **_kwargs: [{"id": 1, "name": "Existing"}])
        monkeypatch.setattr(paperless, "create_tag", lambda *_args, **_kwargs: {"id": 2, "name": "PendingTag"})
        monkeypatch.setattr(paperless, "list_all_correspondents", lambda *_args, **_kwargs: [])
        monkeypatch.setattr(paperless, "create_correspondent", lambda *_args, **_kwargs: {"id": 77, "name": "New Corr"})
        patched: list[dict[str, Any]] = []
        monkeypatch.setattr(
            paperless,
            "update_document",
            lambda _settings, _doc_id, payload: patched.append(dict(payload)),
        )

        call = WritebackDryRunCall(
            doc_id=1201,
            method="PATCH",
            path="/api/documents/1201/",
            payload={
                "title": "Updated",
                "tags": [1],
                "pending_tag_names": ["PendingTag"],
                "correspondent": None,
                "pending_correspondent_name": "New Corr",
            },
        )
        execute_writeback_call(settings, db, call)
        db.commit()

        assert patched
        sent = patched[0]
        assert sent.get("title") == "Updated"
        assert sent.get("correspondent") == 77
        assert sent.get("tags") == [1, 2]

        local_doc = db.get(Document, 1201)
        assert local_doc is not None
        assert local_doc.correspondent_id == 77
        assert sorted([tag.id for tag in local_doc.tags]) == [1, 2]
        pending_corr = db.query(DocumentPendingCorrespondent).filter(DocumentPendingCorrespondent.doc_id == 1201).one_or_none()
        assert pending_corr is None


def test_execute_writeback_call_post_and_delete_paths(
    session_factory: Any, monkeypatch: Any
) -> None:
    from app.services.integrations import paperless

    settings = load_settings()
    with session_factory() as db:
        notes: list[tuple[str, int, int]] = []
        monkeypatch.setattr(
            paperless,
            "add_document_note",
            lambda _settings, doc_id, note: notes.append(("add", int(doc_id), len(str(note)))),
        )
        monkeypatch.setattr(
            paperless,
            "delete_document_note",
            lambda _settings, doc_id, note_id: notes.append(("del", int(doc_id), int(note_id))),
        )

        execute_writeback_call(
            settings,
            db,
            WritebackDryRunCall(doc_id=1202, method="POST", path="/api/documents/1202/notes/", payload={"note": "hello"}),
        )
        execute_writeback_call(
            settings,
            db,
            WritebackDryRunCall(doc_id=1202, method="DELETE", path="/api/documents/1202/notes/?id=55", payload={}),
        )
        execute_writeback_call(
            settings,
            db,
            WritebackDryRunCall(doc_id=1202, method="DELETE", path="/api/documents/1202/notes/66/", payload={}),
        )

        assert ("add", 1202, 5) in notes
        assert ("del", 1202, 55) in notes
        assert ("del", 1202, 66) in notes


def test_execute_writeback_call_delete_raises_for_invalid_note_path(
    session_factory: Any,
) -> None:
    settings = load_settings()
    with session_factory() as db:
        try:
            execute_writeback_call(
                settings,
                db,
                WritebackDryRunCall(doc_id=1203, method="DELETE", path="/api/documents/1203/notes/no-id", payload={}),
            )
        except RuntimeError as exc:
            assert "Cannot parse note id" in str(exc)
        else:
            raise AssertionError("Expected RuntimeError for invalid note path")
