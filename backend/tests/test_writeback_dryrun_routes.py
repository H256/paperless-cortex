from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Document


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

