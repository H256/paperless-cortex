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

