from __future__ import annotations

from types import SimpleNamespace

from app.config import load_settings
from app.models import Document, DocumentNote
from app.routes.sync import _merge_document_notes, _upsert_document
from app.schemas import DocumentIn


def test_upsert_document_notes_is_idempotent(session_factory):
    settings = load_settings()
    payload = {
        "id": 1959,
        "title": "Test doc",
        "content": "abc",
        "correspondent": None,
        "document_type": None,
        "document_date": None,
        "created": "2026-02-12T10:00:00+00:00",
        "modified": "2026-02-12T10:00:00+00:00",
        "added": None,
        "deleted_at": None,
        "archive_serial_number": None,
        "original_file_name": None,
        "mime_type": None,
        "page_count": 1,
        "owner": None,
        "user_can_change": True,
        "is_shared_by_requester": False,
        "notes": [
            {
                "id": 12880,
                "note": "original",
                "created": "2026-02-10T18:44:30.261279+01:00",
                "user": {"id": 4, "username": "klemens", "first_name": "Klemens", "last_name": "Wittig"},
            }
        ],
        "tags": [],
    }
    data = DocumentIn.model_validate(payload)
    cache = {"correspondents": set(), "document_types": set(), "tags": set()}

    with session_factory() as db:
        _upsert_document(db, settings, data, cache)
        db.commit()

        # Re-upsert same note id with updated body must update in-place, not reinsert duplicate PK.
        payload["notes"][0]["note"] = "updated"
        data_updated = DocumentIn.model_validate(payload)
        _upsert_document(db, settings, data_updated, cache)
        db.commit()

        doc = db.get(Document, 1959)
        assert doc is not None
        notes = db.query(DocumentNote).filter(DocumentNote.document_id == 1959).all()
        assert len(notes) == 1
        assert notes[0].id == 12880
        assert notes[0].note == "updated"


def test_upsert_document_notes_remaps_legacy_positive_collision(session_factory):
    settings = load_settings()
    cache = {"correspondents": set(), "document_types": set(), "tags": set()}
    with session_factory() as db:
        # Existing legacy local AI note accidentally used positive id namespace.
        doc_old = Document(id=1001, title="old")
        db.add(doc_old)
        db.flush()
        db.add(
            DocumentNote(
                id=12880,
                document_id=1001,
                note="Legacy local summary\n\nKI-Zusammenfassung",
                created="2026-02-10T10:00:00+00:00",
            )
        )
        db.commit()

        incoming = DocumentIn.model_validate(
            {
                "id": 1959,
                "title": "Remote doc",
                "content": "abc",
                "correspondent": None,
                "document_type": None,
                "document_date": None,
                "created": "2026-02-12T10:00:00+00:00",
                "modified": "2026-02-12T10:00:00+00:00",
                "added": None,
                "deleted_at": None,
                "archive_serial_number": None,
                "original_file_name": None,
                "mime_type": None,
                "page_count": 1,
                "owner": None,
                "user_can_change": True,
                "is_shared_by_requester": False,
                "notes": [
                    {
                        "id": 12880,
                        "note": "Remote note",
                        "created": "2026-02-12T10:00:00+00:00",
                        "user": {"id": 4, "username": "klemens"},
                    }
                ],
                "tags": [],
            }
        )
        _upsert_document(db, settings, incoming, cache)
        db.commit()

        remote_note = db.get(DocumentNote, 12880)
        assert remote_note is not None
        assert int(remote_note.document_id) == 1959
        moved = (
            db.query(DocumentNote)
            .filter(DocumentNote.document_id == 1001, DocumentNote.id < 0)
            .first()
        )
        assert moved is not None


def test_upsert_document_notes_ignores_duplicate_ids_in_single_payload(session_factory):
    settings = load_settings()
    cache = {"correspondents": set(), "document_types": set(), "tags": set()}
    payload = {
        "id": 1959,
        "title": "Test doc",
        "content": "abc",
        "correspondent": None,
        "document_type": None,
        "document_date": None,
        "created": "2026-02-12T10:00:00+00:00",
        "modified": "2026-02-12T10:00:00+00:00",
        "added": None,
        "deleted_at": None,
        "archive_serial_number": None,
        "original_file_name": None,
        "mime_type": None,
        "page_count": 1,
        "owner": None,
        "user_can_change": True,
        "is_shared_by_requester": False,
        "notes": [
            {
                "id": 12880,
                "note": "first",
                "created": "2026-02-10T18:44:30.261279+01:00",
                "user": {"id": 4, "username": "klemens"},
            },
            {
                "id": 12880,
                "note": "duplicate should be ignored",
                "created": "2026-02-10T18:44:30.261279+01:00",
                "user": {"id": 4, "username": "klemens"},
            },
        ],
        "tags": [],
    }
    data = DocumentIn.model_validate(payload)

    with session_factory() as db:
        _upsert_document(db, settings, data, cache)
        db.commit()

        notes = db.query(DocumentNote).filter(DocumentNote.document_id == 1959).all()
        assert len(notes) == 1
        assert notes[0].id == 12880
        assert notes[0].note == "first"


def test_upsert_document_notes_skips_malformed_note_ids(session_factory):
    with session_factory() as db:
        doc = Document(id=1959, title="Test doc")
        db.add(doc)
        db.flush()
        incoming_notes = [
            SimpleNamespace(
                id=12880,
                note="valid",
                created="2026-02-10T18:44:30.261279+01:00",
                user={"id": 4, "username": "klemens"},
            ),
            SimpleNamespace(
                id="broken-id",
                note="invalid",
                created="2026-02-10T18:44:30.261279+01:00",
                user={"id": 4, "username": "klemens"},
            ),
        ]
        _merge_document_notes(db, doc, incoming_notes)
        db.commit()

        notes = db.query(DocumentNote).filter(DocumentNote.document_id == 1959).all()
        assert len(notes) == 1
        assert notes[0].id == 12880
        assert notes[0].note == "valid"
