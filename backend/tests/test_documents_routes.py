from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import (
    Document,
    DocumentEmbedding,
    DocumentNote,
    DocumentPageAnchor,
    DocumentPageText,
    DocumentPendingTag,
    DocumentSuggestion,
    SuggestionAudit,
    TaskRun,
)


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


def _insert_local_document(
    doc_id: int,
    title: str,
    created: str,
    *,
    correspondent_id: int | None = None,
):
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(
            Document(
                id=doc_id,
                title=title,
                created=created,
                modified=created,
                correspondent_id=correspondent_id,
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


def _insert_suggestion(doc_id: int, source: str, payload: str):
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(
            DocumentSuggestion(
                doc_id=doc_id,
                source=source,
                payload=payload,
                created_at="2026-02-10T10:20:00+00:00",
                processed_at="2026-02-10T10:20:00+00:00",
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


def test_list_documents_filter_without_correspondent(api_client, monkeypatch):
    from app.services import paperless

    monkeypatch.setattr(
        paperless,
        "list_documents",
        lambda *args, **kwargs: {
            "count": 2,
            "next": None,
            "previous": None,
            "results": [
                {"id": 11, "title": "No Corr", "correspondent": None, "tags": []},
                {"id": 12, "title": "Has Corr", "correspondent": 3, "tags": []},
            ],
        },
    )
    monkeypatch.setattr(
        paperless,
        "list_documents_cached",
        lambda *args, **kwargs: {
            "count": 2,
            "next": None,
            "previous": None,
            "results": [
                {"id": 11, "title": "No Corr", "correspondent": None, "tags": []},
                {"id": 12, "title": "Has Corr", "correspondent": 3, "tags": []},
            ],
        },
    )

    response = api_client.get("/documents", params={"correspondent__id": -1})
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert len(payload["results"]) == 1
    assert payload["results"][0]["id"] == 11
    assert payload["results"][0]["correspondent"] is None


def test_document_pipeline_fanout_returns_ordered_items(api_client, monkeypatch):
    from app.services import paperless

    _insert_local_document(doc_id=21, title="Fanout Doc", created="2026-02-10T10:00:00+00:00")
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        doc = db.get(Document, 21)
        assert doc is not None
        doc.modified = "2026-02-10T10:00:00+00:00"
        db.add(
            TaskRun(
                doc_id=21,
                task="vision_ocr",
                source=None,
                status="running",
                worker_id="worker:test",
                attempt=1,
                checkpoint_json='{"stage":"vision_ocr","current":5,"total":20}',
                started_at="2026-02-12T10:00:00+00:00",
                created_at="2026-02-12T10:00:00+00:00",
                updated_at="2026-02-12T10:00:00+00:00",
            )
        )
        db.commit()

    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda *args, **kwargs: {"id": 21, "modified": "2026-02-10T09:00:00+00:00"},
    )

    response = api_client.get("/documents/21/pipeline-fanout")
    assert response.status_code == 200
    payload = response.json()
    assert payload["doc_id"] == 21
    assert isinstance(payload["items"], list)
    assert len(payload["items"]) > 0
    assert payload["items"][0]["order"] == 1
    assert any(item["task"] == "sync" for item in payload["items"])
    vision_item = next((item for item in payload["items"] if item["task"] == "vision_ocr"), None)
    assert vision_item is not None
    assert vision_item["status"] in {"running", "missing", "done", "failed", "retrying"}


def _insert_local_note(doc_id: int, note: str, note_id: int = -1):
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(
            DocumentNote(
                id=note_id,
                document_id=doc_id,
                note=note,
                created="2026-02-10T10:15:00+00:00",
            )
        )
        db.commit()


def test_pipeline_status_ignores_metadata_only_modified_for_processing(api_client, monkeypatch):
    from app.services import paperless

    _insert_local_document(doc_id=31, title="Stable Doc", created="2026-02-10T10:00:00+00:00")
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        doc = db.get(Document, 31)
        assert doc is not None
        # Simulate metadata-only update (e.g. writeback) after existing processing artifacts.
        doc.modified = "2026-02-12T10:00:00+00:00"
        doc.page_count = 1
        db.add(
            DocumentEmbedding(
                doc_id=31,
                embedding_source="both",
                embedded_at="2026-02-10T10:05:00+00:00",
                chunk_count=5,
            )
        )
        db.add(
            DocumentPageText(
                doc_id=31,
                page=1,
                source="vision_ocr",
                text="Vision text",
                created_at="2026-02-10T10:04:00+00:00",
                processed_at="2026-02-10T10:04:00+00:00",
            )
        )
        db.add(
            DocumentPageAnchor(
                doc_id=31,
                page=1,
                source="paperless_pdf",
                anchors_json='[{"text":"Stable","bbox":[1,2,3,4]}]',
                token_count=1,
                status="ok",
                created_at="2026-02-10T10:04:00+00:00",
                processed_at="2026-02-10T10:04:00+00:00",
            )
        )
        db.add(
            DocumentSuggestion(
                doc_id=31,
                source="paperless_ocr",
                payload='{"title":"Stable Doc"}',
                created_at="2026-02-10T10:06:00+00:00",
                processed_at="2026-02-10T10:06:00+00:00",
            )
        )
        db.add(
            DocumentSuggestion(
                doc_id=31,
                source="vision_ocr",
                payload='{"title":"Stable Doc"}',
                created_at="2026-02-10T10:06:00+00:00",
                processed_at="2026-02-10T10:06:00+00:00",
            )
        )
        db.commit()

    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda *args, **kwargs: {"id": 31, "modified": "2026-02-12T10:00:00+00:00"},
    )

    response = api_client.get("/documents/31/pipeline-status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["sync_ok"] is True
    assert payload["paperless_ok"] is True
    assert payload["missing_tasks"] == []


def test_pipeline_status_marks_evidence_optional_for_no_text_layer(api_client, monkeypatch):
    from app.services import paperless

    _insert_local_document(doc_id=32, title="Image Only", created="2026-02-10T10:00:00+00:00")
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        doc = db.get(Document, 32)
        assert doc is not None
        doc.page_count = 1
        db.add(
            DocumentPageAnchor(
                doc_id=32,
                page=1,
                source="paperless_pdf",
                anchors_json="[]",
                token_count=0,
                status="no_text_layer",
                created_at="2026-02-10T10:04:00+00:00",
                processed_at="2026-02-10T10:04:00+00:00",
            )
        )
        db.commit()

    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda *args, **kwargs: {"id": 32, "modified": "2026-02-10T10:00:00+00:00"},
    )

    response = api_client.get("/documents/32/pipeline-status")
    assert response.status_code == 200
    payload = response.json()
    evidence_step = next((item for item in payload["steps"] if item["key"] == "evidence"), None)
    assert evidence_step is not None
    assert evidence_step["required"] is False
    assert evidence_step["done"] is True
    assert payload["evidence_ok"] is True
    assert all(task.get("task") != "evidence_index" for task in payload["missing_tasks"])


def test_get_local_document_note_override_sets_needs_review(api_client, monkeypatch):
    from app.services import paperless

    _insert_local_document(doc_id=41, title="Doc 41", created="2026-02-10T10:00:00+00:00")
    _insert_local_note(
        doc_id=41,
        note="Local summary text\n\nModel:gpt\nKI-Zusammenfassung",
        note_id=-41,
    )
    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda *args, **kwargs: {
            "id": 41,
            "title": "Doc 41",
            "created": "2026-02-10T10:00:00+00:00",
            "modified": "2026-02-10T10:00:00+00:00",
            "correspondent": None,
            "tags": [],
            "notes": [],
        },
    )

    response = api_client.get("/documents/41/local")
    assert response.status_code == 200
    payload = response.json()
    assert payload["local_overrides"] is True
    assert payload["review_status"] == "needs_review"


def test_list_documents_detects_correspondent_clear_as_override(api_client, monkeypatch):
    from app.services import paperless

    _insert_local_document(
        doc_id=42,
        title="Doc 42",
        created="2026-02-10T10:00:00+00:00",
        correspondent_id=None,
    )
    monkeypatch.setattr(
        paperless,
        "list_documents",
        lambda *args, **kwargs: {
            "count": 1,
            "next": None,
            "previous": None,
            "results": [
                {
                    "id": 42,
                    "title": "Doc 42",
                    "created": "2026-02-10T10:00:00+00:00",
                    "modified": "2026-02-10T10:00:00+00:00",
                    "correspondent": 7,
                    "tags": [],
                },
            ],
        },
    )

    response = api_client.get("/documents", params={"include_derived": True, "review_status": "needs_review"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["results"][0]["id"] == 42
    assert payload["results"][0]["local_overrides"] is True
    assert payload["results"][0]["review_status"] == "needs_review"


def test_get_local_document_detects_empty_title_as_override(api_client, monkeypatch):
    from app.services import paperless

    _insert_local_document(doc_id=43, title="", created="2026-02-10T10:00:00+00:00")
    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda *args, **kwargs: {
            "id": 43,
            "title": "Remote title",
            "created": "2026-02-10T10:00:00+00:00",
            "modified": "2026-02-10T10:00:00+00:00",
            "correspondent": None,
            "tags": [],
            "notes": [],
        },
    )

    response = api_client.get("/documents/43/local")
    assert response.status_code == 200
    payload = response.json()
    assert payload["local_overrides"] is True
    assert payload["review_status"] == "needs_review"


def test_list_documents_summary_preview_only_when_requested(api_client, monkeypatch):
    from app.services import paperless

    _insert_suggestion(
        doc_id=44,
        source="paperless_ocr",
        payload='{"summary":"Kurzfassung fuer Vorschau","title":"Doc 44"}',
    )
    monkeypatch.setattr(
        paperless,
        "list_documents",
        lambda *args, **kwargs: {
            "count": 1,
            "next": None,
            "previous": None,
            "results": [
                {
                    "id": 44,
                    "title": "Doc 44",
                    "created": "2026-02-10T10:00:00+00:00",
                    "modified": "2026-02-10T10:00:00+00:00",
                    "correspondent": None,
                    "tags": [],
                },
            ],
        },
    )

    without_preview = api_client.get("/documents", params={"include_derived": True})
    assert without_preview.status_code == 200
    without_payload = without_preview.json()
    assert without_payload["count"] == 1
    assert without_payload["results"][0].get("ai_summary_preview") in (None, "")

    with_preview = api_client.get(
        "/documents",
        params={"include_derived": True, "include_summary_preview": True},
    )
    assert with_preview.status_code == 200
    with_payload = with_preview.json()
    assert with_payload["count"] == 1
    assert with_payload["results"][0].get("ai_summary_preview") == "Kurzfassung fuer Vorschau"
