from __future__ import annotations

import os
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Document


def _insert_document(doc_id: int, title: str) -> None:
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(Document(id=doc_id, title=title))
        db.commit()


def test_writeback_job_replay_skips_applied_calls(api_client: Any, monkeypatch: Any) -> None:
    """A job that has already applied calls must skip them on re-execution.

    This is the idempotent-replay follow-up to WB-001 (#110): PR #245 made
    remote 404s idempotent, but a replayed job would still re-apply calls that
    had already succeeded. Applied call indexes are now tracked so a replay
    skips them.
    """
    from app.services.integrations import paperless

    _insert_document(601, "Local title 601")

    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda _settings, doc_id: {
            "id": doc_id,
            "title": "Remote title 601",
            "document_date": None,
            "correspondent": None,
            "tags": [],
            "notes": [],
        },
    )

    calls: dict[str, int] = {"patch": 0}

    def _fake_patch(_settings: Any, doc_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        calls["patch"] += 1
        return {"id": doc_id, **payload}

    monkeypatch.setattr(paperless, "update_document", _fake_patch)
    monkeypatch.setattr(paperless, "add_document_note", lambda *a, **k: {"id": 1})
    monkeypatch.setattr(paperless, "delete_document_note", lambda *a, **k: None)
    monkeypatch.setenv("WRITEBACK_EXECUTE_ENABLED", "1")

    create_resp = api_client.post("/writeback/jobs", json={"doc_ids": [601]})
    assert create_resp.status_code == 200
    job_id = int(create_resp.json()["id"])

    # First real execution applies the calls.
    first = api_client.post(f"/writeback/jobs/{job_id}/execute", json={"dry_run": False})
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["status"] == "completed"
    assert calls["patch"] >= 1
    first_patch_count = calls["patch"]
    assert first_body["applied_calls_count"] >= 1

    # Re-execute the same job: already-applied calls must be skipped, so the
    # remote patch is not called again.
    second = api_client.post(f"/writeback/jobs/{job_id}/execute", json={"dry_run": False})
    assert second.status_code == 200
    second_body = second.json()
    assert second_body["status"] == "completed"
    assert calls["patch"] == first_patch_count, (
        "Replayed job re-applied calls that were already applied"
    )
    assert second_body["applied_calls_count"] == first_body["applied_calls_count"]


def test_writeback_job_detail_reports_applied_count(api_client: Any, monkeypatch: Any) -> None:
    """GET /jobs/{id} exposes applied_calls_count for a completed job."""
    from app.services.integrations import paperless

    _insert_document(602, "Local title 602")

    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda _settings, doc_id: {
            "id": doc_id,
            "title": "Remote title 602",
            "document_date": None,
            "correspondent": None,
            "tags": [],
            "notes": [],
        },
    )
    monkeypatch.setattr(
        paperless, "update_document", lambda _s, d, p: {"id": d, **p}
    )
    monkeypatch.setattr(paperless, "add_document_note", lambda *a, **k: {"id": 1})
    monkeypatch.setattr(paperless, "delete_document_note", lambda *a, **k: None)
    monkeypatch.setenv("WRITEBACK_EXECUTE_ENABLED", "1")

    create_resp = api_client.post("/writeback/jobs", json={"doc_ids": [602]})
    assert create_resp.status_code == 200
    job_id = int(create_resp.json()["id"])

    api_client.post(f"/writeback/jobs/{job_id}/execute", json={"dry_run": False})

    detail = api_client.get(f"/writeback/jobs/{job_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert "applied_calls_count" in body
    assert body["applied_calls_count"] >= 1


def test_parse_applied_call_indexes_handles_malformed() -> None:
    from app.services.writeback.writeback_selection import (
        parse_applied_call_indexes,
        serialize_applied_call_indexes,
    )

    assert parse_applied_call_indexes(None) == set()
    assert parse_applied_call_indexes("") == set()
    assert parse_applied_call_indexes("not-json") == set()
    assert parse_applied_call_indexes("[1, 2, 3]") == {1, 2, 3}
    # Non-int entries are ignored.
    assert parse_applied_call_indexes('[1, "x", null, 2]') == {1, 2}
    # Round-trip.
    assert parse_applied_call_indexes(serialize_applied_call_indexes({3, 1})) == {1, 3}
