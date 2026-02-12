from __future__ import annotations

from app.config import load_settings
from app.models import Document, DocumentNote
from app.routes.sync import _upsert_document
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

