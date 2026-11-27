from __future__ import annotations

import os
from typing import Any

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Document, SuggestionAudit


def _audited_doc_ids() -> set[int]:
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        rows = db.query(SuggestionAudit).filter(
            SuggestionAudit.action == "apply_to_document:writeback"
        )
        return {int(row.doc_id) for row in rows}


def test_job_partial_failure_then_retry_audits_every_doc_and_patches_once(
    api_client: Any, monkeypatch: Any
) -> None:
    """Job over two docs: the second PATCH fails, then the retry succeeds.

    Each doc must be PATCHed exactly once overall, and both must end up with an
    audit row (the first used to lose it when the run aborted on the second).
    """
    from app.services.integrations import paperless

    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(Document(id=901, title="Local 901"))
        db.add(Document(id=902, title="Local 902"))
        db.commit()
    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda _s, doc_id: {
            "id": doc_id,
            "title": f"Remote {doc_id}",
            "document_date": None,
            "correspondent": None,
            "tags": [],
            "notes": [],
        },
    )
    patched: list[int] = []
    outage = {"on": True}

    def _patch(_s: Any, doc_id: int, _payload: dict[str, Any]) -> dict[str, Any]:
        if doc_id == 902 and outage["on"]:
            raise httpx.ConnectError("paperless unreachable")
        patched.append(int(doc_id))
        return {}

    monkeypatch.setattr(paperless, "update_document", _patch)
    monkeypatch.setenv("WRITEBACK_EXECUTE_ENABLED", "1")

    job_id = api_client.post("/writeback/jobs", json={"doc_ids": [901, 902]}).json()["id"]

    first = api_client.post(f"/writeback/jobs/{job_id}/execute", json={"dry_run": False}).json()
    assert first["status"] == "failed"
    assert patched == [901]
    assert _audited_doc_ids() == {901}, "doc 901 succeeded, so it must keep its audit row"

    outage["on"] = False
    second = api_client.post(f"/writeback/jobs/{job_id}/execute", json={"dry_run": False}).json()
    assert second["status"] == "completed"
    assert patched == [901, 902], "doc 901 must not be PATCHed again on retry"
    assert _audited_doc_ids() == {901, 902}
