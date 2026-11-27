from __future__ import annotations

import os
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Document


def _setup(monkeypatch: Any, remote_title: list[str]) -> list[int]:
    from app.services.integrations import paperless

    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(Document(id=801, title="Local title 801"))
        db.commit()
    patches: list[int] = []
    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda _s, doc_id: {
            "id": doc_id,
            "title": remote_title[0],
            "document_date": None,
            "correspondent": None,
            "tags": [],
            "notes": [],
        },
    )
    monkeypatch.setattr(
        paperless, "update_document", lambda _s, doc_id, _p: patches.append(int(doc_id)) or {}
    )
    monkeypatch.setenv("WRITEBACK_EXECUTE_ENABLED", "1")
    return patches


def test_job_is_refused_when_paperless_changed_after_creation(
    api_client: Any, monkeypatch: Any
) -> None:
    remote_title = ["Remote title v1"]
    patches = _setup(monkeypatch, remote_title)

    job_id = api_client.post("/writeback/jobs", json={"doc_ids": [801]}).json()["id"]
    remote_title[0] = "Someone edited this in Paperless"  # remote moves on after the preview

    result = api_client.post(f"/writeback/jobs/{job_id}/execute", json={"dry_run": False})
    assert result.status_code == 200
    body = result.json()
    assert body["status"] == "failed"
    assert "801" in str(body["error"])
    assert patches == [], "stale job must not overwrite the newer Paperless edit"


def test_job_runs_when_nothing_changed_since_creation(api_client: Any, monkeypatch: Any) -> None:
    remote_title = ["Remote title v1"]
    patches = _setup(monkeypatch, remote_title)

    job_id = api_client.post("/writeback/jobs", json={"doc_ids": [801]}).json()["id"]
    result = api_client.post(f"/writeback/jobs/{job_id}/execute", json={"dry_run": False})
    assert result.json()["status"] == "completed"
    assert patches == [801]


def test_job_without_fingerprint_still_runs(api_client: Any, monkeypatch: Any) -> None:
    """Jobs created before the fingerprint column existed have NULL and are not blocked."""
    from app.models import WritebackJob

    remote_title = ["Remote title v1"]
    patches = _setup(monkeypatch, remote_title)
    job_id = api_client.post("/writeback/jobs", json={"doc_ids": [801]}).json()["id"]
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        job = db.get(WritebackJob, job_id)
        assert job is not None
        job.preview_fingerprint_json = None
        db.commit()
    remote_title[0] = "changed"
    result = api_client.post(f"/writeback/jobs/{job_id}/execute", json={"dry_run": False})
    assert result.json()["status"] == "completed"
    assert patches == [801]
