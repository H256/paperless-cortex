from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import WritebackJob
from app.services.writeback.writeback_jobs import is_stale_running_job


def _job(status: str, started_at: str | None) -> WritebackJob:
    return WritebackJob(
        status=status,
        dry_run=False,
        docs_selected=1,
        docs_changed=1,
        calls_count=1,
        doc_ids_json=json.dumps([701]),
        calls_json="[]",
        created_at="2026-01-01T00:00:00+00:00",
        started_at=started_at,
    )


def _iso(minutes_ago: int) -> str:
    return (datetime.now(UTC) - timedelta(minutes=minutes_ago)).isoformat()


def test_staleness_rules() -> None:
    assert is_stale_running_job(_job("running", _iso(31))) is True
    assert is_stale_running_job(_job("running", _iso(1))) is False
    assert is_stale_running_job(_job("running", None)) is True
    assert is_stale_running_job(_job("running", "not-a-date")) is True
    assert is_stale_running_job(_job("pending", _iso(500))) is False
    assert is_stale_running_job(_job("failed", _iso(500))) is False


def _insert_running_job(started_at: str) -> int:
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        job = _job("running", started_at)
        db.add(job)
        db.commit()
        return int(job.id)


def test_stale_running_job_can_be_deleted_fresh_one_cannot(api_client: Any) -> None:
    fresh = _insert_running_job(_iso(1))
    stale = _insert_running_job(_iso(120))
    assert api_client.delete(f"/writeback/jobs/{fresh}").status_code == 409
    response = api_client.delete(f"/writeback/jobs/{stale}")
    assert response.status_code == 200
    assert response.json()["removed"] is True


def test_create_job_retires_stale_running_job_and_creates_new(
    api_client: Any, monkeypatch: Any
) -> None:
    from app.models import Document
    from app.services.integrations import paperless

    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(Document(id=701, title="Local title 701"))
        db.commit()
    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda _settings, doc_id: {
            "id": doc_id,
            "title": "Remote title 701",
            "document_date": None,
            "correspondent": None,
            "tags": [],
            "notes": [],
        },
    )
    stale_id = _insert_running_job(_iso(120))

    created = api_client.post("/writeback/jobs", json={"doc_ids": [701]})
    assert created.status_code == 200
    assert created.json()["id"] != stale_id

    with Session(engine) as db:
        stale = db.get(WritebackJob, stale_id)
        assert stale is not None and stale.status == "failed"

    # A second request now deduplicates against the new pending job, not the retired one.
    again = api_client.post("/writeback/jobs", json={"doc_ids": [701]})
    assert again.json()["id"] == created.json()["id"]
