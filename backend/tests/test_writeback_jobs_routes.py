from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Document


def _insert_document(doc_id: int, title: str):
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(Document(id=doc_id, title=title))
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
