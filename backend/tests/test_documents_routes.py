from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Document, DocumentPendingTag, SuggestionAudit


def _insert_suggestion_audit(
    doc_id: int,
    created_at: str,
    action: str = "apply_to_document:title",
):
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(
            SuggestionAudit(
                doc_id=doc_id,
                action=action,
                source="paperless_ocr",
                field="title",
                old_value="old",
                new_value="new",
                created_at=created_at,
            )
        )
        db.commit()


def _insert_local_document(doc_id: int, title: str, created: str):
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(
            Document(
                id=doc_id,
                title=title,
                created=created,
                modified=created,
            )
        )
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


def test_get_local_document_missing(api_client):
    response = api_client.get("/documents/999/local")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "missing"


def test_process_missing_queue_disabled(api_client):
    response = api_client.post("/documents/process-missing", params={"dry_run": True})
    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is False
    assert payload["dry_run"] is True


def test_get_document_suggestions_empty(api_client, monkeypatch):
    from app.services import paperless
    from app.services import meta_cache

    monkeypatch.setattr(paperless, "get_document", lambda *args, **kwargs: {"content": ""})
    monkeypatch.setattr(meta_cache, "get_cached_tags", lambda *args, **kwargs: [])
    monkeypatch.setattr(meta_cache, "get_cached_correspondents", lambda *args, **kwargs: [])

    response = api_client.get("/documents/123/suggestions")
    assert response.status_code == 200
    payload = response.json()
    assert payload["doc_id"] == 123
    assert payload["suggestions"] == {}
    assert payload["suggestions_meta"] == {}


def test_cleanup_texts_queue_disabled(api_client):
    response = api_client.post(
        "/documents/cleanup-texts",
        json={"enqueue": True, "clear_first": True},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["queued"] is False
    assert payload["enqueued"] == 0


def test_list_documents_review_status_unreviewed(api_client, monkeypatch):
    from app.services import paperless

    monkeypatch.setattr(
        paperless,
        "list_documents",
        lambda *args, **kwargs: {
            "count": 2,
            "next": None,
            "previous": None,
            "results": [
                {"id": 1, "title": "Doc A", "modified": "2026-02-10T10:00:00+00:00", "tags": []},
                {"id": 2, "title": "Doc B", "modified": "2026-02-10T10:00:00+00:00", "tags": []},
            ],
        },
    )
    _insert_suggestion_audit(doc_id=2, created_at="2026-02-10T10:05:00+00:00")

    response = api_client.get("/documents", params={"include_derived": True, "review_status": "unreviewed"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert len(payload["results"]) == 1
    assert payload["results"][0]["id"] == 1
    assert payload["results"][0]["review_status"] == "unreviewed"


def test_list_documents_review_status_needs_review(api_client, monkeypatch):
    from app.services import paperless

    monkeypatch.setattr(
        paperless,
        "list_documents",
        lambda *args, **kwargs: {
            "count": 1,
            "next": None,
            "previous": None,
            "results": [
                {"id": 3, "title": "Doc C", "modified": "2026-02-10T10:10:00+00:00", "tags": []},
            ],
        },
    )
    _insert_suggestion_audit(doc_id=3, created_at="2026-02-10T10:05:00+00:00")

    response = api_client.get("/documents", params={"include_derived": True, "review_status": "needs_review"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert len(payload["results"]) == 1
    assert payload["results"][0]["id"] == 3
    assert payload["results"][0]["review_status"] == "needs_review"


def test_list_documents_local_overrides_force_needs_review(api_client, monkeypatch):
    from app.services import paperless

    _insert_local_document(doc_id=4, title="Local override title", created="2026-02-10")
    _insert_suggestion_audit(doc_id=4, created_at="2026-02-10T10:20:00+00:00")
    monkeypatch.setattr(
        paperless,
        "list_documents",
        lambda *args, **kwargs: {
            "count": 1,
            "next": None,
            "previous": None,
            "results": [
                {
                    "id": 4,
                    "title": "Remote title",
                    "created": "2026-02-10",
                    "modified": "2026-02-10T10:00:00+00:00",
                    "correspondent": None,
                    "tags": [],
                },
            ],
        },
    )

    response = api_client.get("/documents", params={"include_derived": True, "review_status": "needs_review"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert len(payload["results"]) == 1
    assert payload["results"][0]["id"] == 4
    assert payload["results"][0]["review_status"] == "needs_review"


def test_pending_new_tags_force_needs_review(api_client, monkeypatch):
    from app.services import paperless

    _insert_local_document(doc_id=5, title="Doc 5", created="2026-02-10")
    _insert_pending_tags(doc_id=5, names=["BrandNewTag"])
    _insert_suggestion_audit(doc_id=5, created_at="2026-02-10T10:20:00+00:00")
    monkeypatch.setattr(
        paperless,
        "list_documents",
        lambda *args, **kwargs: {
            "count": 1,
            "next": None,
            "previous": None,
            "results": [
                {
                    "id": 5,
                    "title": "Doc 5",
                    "created": "2026-02-10",
                    "modified": "2026-02-10T10:00:00+00:00",
                    "correspondent": None,
                    "tags": [],
                },
            ],
        },
    )

    response = api_client.get("/documents", params={"include_derived": True, "review_status": "needs_review"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["results"][0]["id"] == 5
    assert payload["results"][0]["review_status"] == "needs_review"
