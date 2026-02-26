from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import (
    Correspondent,
    Document,
    DocumentNote,
    DocumentPendingCorrespondent,
    DocumentPendingTag,
    SuggestionAudit,
    Tag,
)


def _insert_document(doc_id: int):
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(Document(id=doc_id, title="Local title"))
        db.commit()


def test_dry_run_preview_with_doc_id_uses_direct_document(api_client, monkeypatch):
    from app.services import paperless

    _insert_document(123)

    def _list_documents_should_not_run(*args, **kwargs):
        raise AssertionError("list_documents should not be called when doc_id is provided")

    monkeypatch.setattr(paperless, "list_documents", _list_documents_should_not_run)
    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda settings, doc_id: {
            "id": doc_id,
            "title": "Remote title",
            "document_date": None,
            "correspondent": None,
            "tags": [],
            "notes": [],
        },
    )

    response = api_client.get(
        "/writeback/dry-run/preview",
        params={"doc_id": 123, "only_changed": False},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert len(payload["items"]) == 1
    assert payload["items"][0]["doc_id"] == 123


def test_reviewed_timestamp_uses_fresh_remote_document(session_factory, monkeypatch):
    from app.routes.writeback_dryrun import _reviewed_timestamp_for_doc
    from app.services import paperless
    from app.deps import get_settings

    with session_factory() as db:
        db.add(Document(id=321, title="Local", modified="2026-02-14T10:00:00+00:00"))
        db.commit()

        monkeypatch.setattr(
            paperless,
            "get_document_cached",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("cached document read should not be used")),
        )
        monkeypatch.setattr(
            paperless,
            "get_document",
            lambda _settings, _doc_id: {"id": 321, "modified": "2026-02-14T11:11:11+00:00"},
        )

        modified = _reviewed_timestamp_for_doc(get_settings(), db, 321)
        db.commit()

        refreshed = db.get(Document, 321)
        assert modified == "2026-02-14T11:11:11+00:00"
        assert refreshed is not None
        assert refreshed.modified == "2026-02-14T11:11:11+00:00"


def test_dry_run_preview_only_changed_uses_local_audit_candidates(api_client, monkeypatch):
    from app.services import paperless

    _insert_document(501)
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db_doc = db.get(Document, 501)
        assert db_doc is not None
        db_doc.title = "Local changed title"
        db.add(
            SuggestionAudit(
                doc_id=501,
                action="apply_to_document:title",
                source="paperless_ocr",
                created_at="2026-02-14T12:00:00+00:00",
            )
        )
        db.commit()

    def _list_documents_should_not_run(*args, **kwargs):
        raise AssertionError("list_documents should not be called for only_changed preview with local candidates")

    monkeypatch.setattr(paperless, "list_documents", _list_documents_should_not_run)
    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda settings, doc_id: {
            "id": doc_id,
            "title": "Remote original title",
            "created": None,
            "correspondent": None,
            "tags": [],
            "notes": [],
        },
    )

    response = api_client.get(
        "/writeback/dry-run/preview",
        params={"only_changed": True, "page": 1, "page_size": 50},
    )
    assert response.status_code == 200
    payload = response.json()
    ids = [int(item["doc_id"]) for item in payload["items"]]
    assert 501 in ids


def test_execute_now_resolves_pending_correspondent_and_sets_local(api_client, monkeypatch):
    from app.services import paperless

    monkeypatch.setenv("WRITEBACK_EXECUTE_ENABLED", "1")

    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(Document(id=777, title="Doc 777"))
        db.add(
            DocumentPendingCorrespondent(
                doc_id=777,
                name="New Corr",
                updated_at="2026-02-18T20:00:00+00:00",
            )
        )
        db.commit()

    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda settings, doc_id: {
            "id": doc_id,
            "title": "Doc 777",
            "created": None,
            "correspondent": None,
            "tags": [],
            "notes": [],
            "modified": "2026-02-18T20:00:00+00:00",
        },
    )
    monkeypatch.setattr(paperless, "list_all_correspondents", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(paperless, "create_correspondent", lambda *_args, **_kwargs: {"id": "77", "name": "New Corr"})
    patch_payloads: list[dict] = []

    def _update_document(_settings, _doc_id, payload):
        patch_payloads.append(dict(payload))
        return {"id": _doc_id}

    monkeypatch.setattr(paperless, "update_document", _update_document)

    response = api_client.post("/writeback/execute-now", json={"doc_ids": [777]})
    assert response.status_code == 200
    assert patch_payloads
    assert patch_payloads[0].get("correspondent") == 77

    with Session(engine) as db:
        refreshed = db.get(Document, 777)
        pending = db.query(DocumentPendingCorrespondent).filter(DocumentPendingCorrespondent.doc_id == 777).one_or_none()
        corr = db.get(Correspondent, 77)
        assert refreshed is not None
        assert refreshed.correspondent_id == 77
        assert pending is None
        assert corr is not None
        assert (corr.name or "").strip() == "New Corr"


def test_execute_direct_skips_invalid_created_none_and_sets_correspondent(api_client, monkeypatch):
    from app.services import paperless

    monkeypatch.setenv("WRITEBACK_EXECUTE_ENABLED", "1")

    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(Document(id=1869, title="Doc 1869", created=None, document_date=None))
        db.add(
            DocumentPendingCorrespondent(
                doc_id=1869,
                name="Corr 1869",
                updated_at="2026-02-18T20:00:00+00:00",
            )
        )
        db.commit()

    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda settings, doc_id: {
            "id": doc_id,
            "title": "Doc 1869",
            "created": "2026-02-10T10:00:00+00:00",
            "correspondent": None,
            "tags": [],
            "notes": [],
            "modified": "2026-02-18T20:00:00+00:00",
        },
    )
    monkeypatch.setattr(paperless, "list_all_correspondents", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(paperless, "create_correspondent", lambda *_args, **_kwargs: {"id": 18690, "name": "Corr 1869"})
    captured_payloads: list[dict] = []

    def _update_document(_settings, _doc_id, payload):
        captured_payloads.append(dict(payload))
        return {"id": _doc_id}

    monkeypatch.setattr(paperless, "update_document", _update_document)

    response = api_client.post("/writeback/documents/1869/execute-direct", json={})
    assert response.status_code == 200
    assert captured_payloads
    payload = captured_payloads[0]
    assert "created" not in payload
    assert payload.get("correspondent") == 18690


def test_execute_direct_migrates_stale_local_correspondent_id(api_client, monkeypatch):
    from app.services import paperless

    monkeypatch.setenv("WRITEBACK_EXECUTE_ENABLED", "1")

    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(Correspondent(id=9001, name="Legacy Corr"))
        db.add(Document(id=1869, title="Doc 1869", correspondent_id=9001))
        db.add(Document(id=1870, title="Doc 1870", correspondent_id=9001))
        db.commit()

    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda settings, doc_id: {
            "id": doc_id,
            "title": f"Doc {doc_id}",
            "created": None,
            "correspondent": None,
            "tags": [],
            "notes": [],
            "modified": "2026-02-18T20:00:00+00:00",
        },
    )
    monkeypatch.setattr(
        paperless,
        "list_all_correspondents",
        lambda *_args, **_kwargs: [{"id": 9010, "name": "Legacy Corr"}],
    )
    monkeypatch.setattr(
        paperless,
        "create_correspondent",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not create when same name exists")),
    )
    patch_payloads: list[dict] = []

    def _update_document(_settings, _doc_id, payload):
        patch_payloads.append(dict(payload))
        return {"id": _doc_id}

    monkeypatch.setattr(paperless, "update_document", _update_document)

    response = api_client.post("/writeback/documents/1869/execute-direct", json={})
    assert response.status_code == 200
    assert patch_payloads
    assert patch_payloads[0].get("correspondent") == 9010

    with Session(engine) as db:
        d1 = db.get(Document, 1869)
        d2 = db.get(Document, 1870)
        old_corr = db.get(Correspondent, 9001)
        new_corr = db.get(Correspondent, 9010)
        assert d1 is not None and d1.correspondent_id == 9010
        assert d2 is not None and d2.correspondent_id == 9010
        assert old_corr is not None
        assert new_corr is not None
        assert (new_corr.name or "").strip() == "Legacy Corr"


def test_execute_direct_use_paperless_resolutions_sync_local_fields(api_client, monkeypatch):
    from app.services import paperless

    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        tag_a = Tag(id=3001, name="Remote-A")
        tag_b = Tag(id=3002, name="Remote-B")
        corr = Correspondent(id=3003, name="Remote Corr")
        db.add(tag_a)
        db.add(tag_b)
        db.add(corr)
        db.add(
            Document(
                id=1999,
                title="Local title",
                document_date="2025-01-01",
                correspondent_id=None,
            )
        )
        db.add(
            DocumentPendingTag(
                doc_id=1999,
                names_json='["Pending-X"]',
                updated_at="2026-02-20T10:00:00+00:00",
            )
        )
        db.add(
            DocumentPendingCorrespondent(
                doc_id=1999,
                name="Pending Corr",
                updated_at="2026-02-20T10:00:00+00:00",
            )
        )
        db.add(
            DocumentNote(
                id=-1999,
                document_id=1999,
                note="Local summary\nKI-Zusammenfassung",
                created="2026-02-20T10:00:00+00:00",
            )
        )
        db.commit()

    monkeypatch.setenv("WRITEBACK_EXECUTE_ENABLED", "1")
    monkeypatch.setattr(
        paperless,
        "get_document_cached",
        lambda _settings, _doc_id: {
            "id": 1999,
            "title": "Remote title",
            "created": "2026-02-02",
            "modified": "2026-02-20T11:00:00+00:00",
            "correspondent": 3003,
            "tags": [3001, 3002],
            "notes": [{"id": 4001, "note": "Remote summary\nKI-Zusammenfassung"}],
        },
    )

    response = api_client.post(
        "/writeback/documents/1999/execute-direct",
        json={
            "known_paperless_modified": "2026-02-19T10:00:00+00:00",
            "resolutions": {
                "title": "use_paperless",
                "issue_date": "use_paperless",
                "correspondent": "use_paperless",
                "tags": "use_paperless",
                "note": "use_paperless",
            },
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["calls_count"] == 0
    assert payload["doc_ids"] == []

    with Session(engine) as db:
        doc = db.get(Document, 1999)
        assert doc is not None
        assert doc.title == "Remote title"
        assert doc.document_date == "2026-02-02"
        assert doc.correspondent_id == 3003
        assert sorted([tag.id for tag in doc.tags]) == [3001, 3002]
        pending_tags = db.query(DocumentPendingTag).filter(DocumentPendingTag.doc_id == 1999).one_or_none()
        pending_corr = db.query(DocumentPendingCorrespondent).filter(DocumentPendingCorrespondent.doc_id == 1999).one_or_none()
        assert pending_tags is None
        assert pending_corr is None
        ai_notes = db.query(DocumentNote).filter(DocumentNote.document_id == 1999).all()
        ai_texts = [str(note.note or "") for note in ai_notes]
        assert any("Remote summary" in text for text in ai_texts)
