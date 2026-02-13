from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Document, DocumentPendingTag, SuggestionAudit, Tag


def _insert_document(doc_id: int, title: str):
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(Document(id=doc_id, title=title))
        db.commit()


def _insert_tag(tag_id: int, name: str):
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(Tag(id=tag_id, name=name))
        db.commit()


def _insert_pending_tags(doc_id: int, names: list[str]):
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(
            DocumentPendingTag(
                doc_id=doc_id,
                names_json=__import__("json").dumps(names, ensure_ascii=False),
                updated_at="2026-02-10T10:10:00+00:00",
            )
        )
        db.commit()


def test_writeback_job_create_and_execute_dry_run(api_client, monkeypatch):
    from app.services import paperless

    _insert_document(501, "Local title")

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

    create_resp = api_client.post("/writeback/jobs", json={"doc_ids": [501]})
    assert create_resp.status_code == 200
    created = create_resp.json()
    assert created["status"] == "pending"
    assert created["docs_selected"] == 1
    assert created["docs_changed"] == 1
    assert created["calls_count"] >= 1

    job_id = int(created["id"])
    exec_resp = api_client.post(f"/writeback/jobs/{job_id}/execute", json={"dry_run": True})
    assert exec_resp.status_code == 200
    executed = exec_resp.json()
    assert executed["id"] == job_id
    assert executed["status"] == "completed"
    assert executed["dry_run"] is True


def test_writeback_job_execute_real_calls_paperless(api_client, monkeypatch):
    from app.services import paperless

    _insert_document(502, "Local title 502")

    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda settings, doc_id: {
            "id": doc_id,
            "title": "Remote title 502",
            "document_date": None,
            "correspondent": None,
            "tags": [],
            "notes": [],
        },
    )

    calls = {"patch": 0}

    def _fake_patch(settings, doc_id, payload):
        calls["patch"] += 1
        return {"id": doc_id, **payload}

    monkeypatch.setattr(paperless, "update_document", _fake_patch)
    monkeypatch.setattr(paperless, "add_document_note", lambda *args, **kwargs: {"id": 1})
    monkeypatch.setattr(paperless, "delete_document_note", lambda *args, **kwargs: None)
    monkeypatch.setenv("WRITEBACK_EXECUTE_ENABLED", "1")

    create_resp = api_client.post("/writeback/jobs", json={"doc_ids": [502]})
    assert create_resp.status_code == 200
    job_id = int(create_resp.json()["id"])

    exec_resp = api_client.post(f"/writeback/jobs/{job_id}/execute", json={"dry_run": False})
    assert exec_resp.status_code == 200
    executed = exec_resp.json()
    assert executed["status"] == "completed"
    assert executed["dry_run"] is False
    assert calls["patch"] >= 1


def test_writeback_job_create_deduplicates_pending(api_client, monkeypatch):
    from app.services import paperless

    _insert_document(503, "Local title 503")
    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda settings, doc_id: {
            "id": doc_id,
            "title": "Remote title 503",
            "document_date": None,
            "correspondent": None,
            "tags": [],
            "notes": [],
        },
    )

    first = api_client.post("/writeback/jobs", json={"doc_ids": [503]})
    second = api_client.post("/writeback/jobs", json={"doc_ids": [503]})
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]


def test_writeback_execute_pending_runs_all(api_client, monkeypatch):
    from app.services import paperless

    _insert_document(504, "Local title 504")
    _insert_document(505, "Local title 505")
    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda settings, doc_id: {
            "id": doc_id,
            "title": f"Remote title {doc_id}",
            "document_date": None,
            "correspondent": None,
            "tags": [],
            "notes": [],
        },
    )

    api_client.post("/writeback/jobs", json={"doc_ids": [504]})
    api_client.post("/writeback/jobs", json={"doc_ids": [505]})

    result = api_client.post("/writeback/jobs/execute-pending", json={"dry_run": True, "limit": 0})
    assert result.status_code == 200
    payload = result.json()
    assert payload["processed"] >= 2
    assert payload["completed"] >= 2
    assert payload["failed"] == 0


def test_writeback_execute_now_executes_without_queue(api_client, monkeypatch):
    from app.services import paperless

    _insert_document(506, "Local title 506")
    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda settings, doc_id: {
            "id": doc_id,
            "title": "Remote title 506",
            "created": None,
            "correspondent": None,
            "tags": [],
            "notes": [],
        },
    )
    calls = {"patch": 0}

    def _fake_patch(settings, doc_id, payload):
        calls["patch"] += 1
        return {"id": doc_id, **payload}

    monkeypatch.setattr(paperless, "update_document", _fake_patch)
    monkeypatch.setattr(paperless, "add_document_note", lambda *args, **kwargs: {"id": 1})
    monkeypatch.setattr(paperless, "delete_document_note", lambda *args, **kwargs: None)
    monkeypatch.setenv("WRITEBACK_EXECUTE_ENABLED", "1")

    result = api_client.post("/writeback/execute-now", json={"doc_ids": [506]})
    assert result.status_code == 200
    payload = result.json()
    assert payload["docs_selected"] == 1
    assert payload["docs_changed"] == 1
    assert payload["calls_count"] >= 1
    assert calls["patch"] >= 1


def test_writeback_execute_now_updates_local_modified_and_review_timestamp(api_client, monkeypatch):
    from app.services import paperless

    _insert_document(510, "Local title 510")
    remote_modified = "2026-02-12T18:00:00+00:00"
    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda settings, doc_id: {
            "id": doc_id,
            "title": "Remote title 510",
            "created": "2026-02-01",
            "modified": remote_modified,
            "correspondent": None,
            "tags": [],
            "notes": [],
        },
    )
    monkeypatch.setattr(
        paperless,
        "update_document",
        lambda settings, doc_id, payload: {"id": doc_id, **payload},
    )
    monkeypatch.setattr(paperless, "add_document_note", lambda *args, **kwargs: {"id": 1})
    monkeypatch.setattr(paperless, "delete_document_note", lambda *args, **kwargs: None)
    monkeypatch.setenv("WRITEBACK_EXECUTE_ENABLED", "1")

    result = api_client.post("/writeback/execute-now", json={"doc_ids": [510]})
    assert result.status_code == 200

    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        doc = db.query(Document).filter(Document.id == 510).one()
        assert doc.modified == remote_modified
        audit = (
            db.query(SuggestionAudit)
            .filter(
                SuggestionAudit.doc_id == 510,
                SuggestionAudit.action == "apply_to_document:writeback",
            )
            .order_by(SuggestionAudit.id.desc())
            .first()
        )
        assert audit is not None
        assert audit.created_at == remote_modified


def test_writeback_direct_requires_resolution_when_modified_changed(api_client, monkeypatch):
    from app.services import paperless

    _insert_document(507, "Local title 507")
    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda settings, doc_id: {
            "id": doc_id,
            "title": "Remote title 507",
            "created": "2026-02-01",
            "modified": "2026-02-10T10:00:00Z",
            "correspondent": None,
            "tags": [],
            "notes": [],
        },
    )
    monkeypatch.setenv("WRITEBACK_EXECUTE_ENABLED", "1")

    result = api_client.post(
        "/writeback/documents/507/execute-direct",
        json={"known_paperless_modified": "2026-02-09T10:00:00Z", "resolutions": {}},
    )
    assert result.status_code == 200
    payload = result.json()
    assert payload["status"] == "conflicts"
    assert isinstance(payload["conflicts"], list)


def test_writeback_execute_now_creates_missing_paperless_tags(api_client, monkeypatch):
    from app.services import paperless
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.models import Document

    _insert_document(508, "Local title 508")
    _insert_tag(901, "Tag-New")
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        doc = db.query(Document).filter(Document.id == 508).first()
        tag = db.query(Tag).filter(Tag.id == 901).first()
        doc.tags = [tag]
        db.commit()

    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda settings, doc_id: {
            "id": doc_id,
            "title": "Remote title 508",
            "created": "2026-02-01",
            "modified": "2026-02-10T10:00:00Z",
            "correspondent": None,
            "tags": [],
            "notes": [],
        },
    )

    monkeypatch.setattr(paperless, "list_all_tags", lambda settings: [])
    monkeypatch.setattr(paperless, "create_tag", lambda settings, name: {"id": 777, "name": name})
    patch_payloads: list[dict] = []
    monkeypatch.setattr(
        paperless,
        "update_document",
        lambda settings, doc_id, payload: patch_payloads.append(payload) or {"id": doc_id, **payload},
    )
    monkeypatch.setattr(paperless, "add_document_note", lambda *args, **kwargs: {"id": 1})
    monkeypatch.setattr(paperless, "delete_document_note", lambda *args, **kwargs: None)
    monkeypatch.setenv("WRITEBACK_EXECUTE_ENABLED", "1")

    result = api_client.post("/writeback/execute-now", json={"doc_ids": [508]})
    assert result.status_code == 200
    assert patch_payloads
    assert patch_payloads[0].get("tags") == [777]


def test_writeback_direct_executes_for_pending_tags_only(api_client, monkeypatch):
    from app.services import paperless
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.models import Document

    _insert_document(509, "Doc 509")
    _insert_pending_tags(509, ["BrandNew"])
    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda settings, doc_id: {
            "id": doc_id,
            "title": "Doc 509",
            "created": "2026-02-01",
            "modified": "2026-02-10T10:00:00Z",
            "correspondent": None,
            "tags": [],
            "notes": [],
        },
    )
    monkeypatch.setattr(paperless, "list_all_tags", lambda settings: [])
    monkeypatch.setattr(paperless, "create_tag", lambda settings, name: {"id": 778, "name": name})
    patch_payloads: list[dict] = []
    monkeypatch.setattr(
        paperless,
        "update_document",
        lambda settings, doc_id, payload: patch_payloads.append(payload) or {"id": doc_id, **payload},
    )
    monkeypatch.setenv("WRITEBACK_EXECUTE_ENABLED", "1")

    result = api_client.post(
        "/writeback/documents/509/execute-direct",
        json={"known_paperless_modified": "2026-02-10T10:00:00Z", "resolutions": {}},
    )
    assert result.status_code == 200
    payload = result.json()
    assert payload["status"] == "completed"
    assert payload["calls_count"] >= 1
    assert patch_payloads
    assert patch_payloads[0].get("tags") == [778]
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        doc = db.query(Document).filter(Document.id == 509).one()
        assert [tag.id for tag in doc.tags] == [778]
        pending = db.query(DocumentPendingTag).filter(DocumentPendingTag.doc_id == 509).one_or_none()
        assert pending is None
