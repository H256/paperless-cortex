from __future__ import annotations

import json
import os
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import (
    Correspondent,
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
) -> None:
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
    analysis_model: str | None = None,
    analysis_processed_at: str | None = None,
) -> None:
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(
            Document(
                id=doc_id,
                title=title,
                created=created,
                modified=created,
                correspondent_id=correspondent_id,
                analysis_model=analysis_model,
                analysis_processed_at=analysis_processed_at,
            )
        )
        db.commit()


def _insert_pending_tags(doc_id: int, names: list[str]) -> None:
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(
            DocumentPendingTag(
                doc_id=doc_id,
                names_json=json.dumps(names, ensure_ascii=False),
                updated_at="2026-02-10T10:10:00+00:00",
            )
        )
        db.commit()


def _insert_suggestion(doc_id: int, source: str, payload: str) -> None:
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


def _insert_page_text(doc_id: int, page: int, source: str, text: str) -> None:
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(
            DocumentPageText(
                doc_id=doc_id,
                page=page,
                source=source,
                text=text,
                raw_text=text,
                clean_text=text,
            )
        )
        db.commit()


def test_get_local_document_missing(api_client: Any) -> None:
    response = api_client.get("/documents/999/local")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "missing"


def test_dashboard_uses_grouped_correspondent_counts(api_client: Any) -> None:
    import app.routes.documents as documents_routes

    documents_routes._DASHBOARD_CACHE["ts"] = 0.0
    documents_routes._DASHBOARD_CACHE["data"] = None

    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        alpha = Correspondent(id=7001, name="Alpha")
        beta = Correspondent(id=7002, name="Beta")
        db.add_all([alpha, beta])
        db.add_all(
            [
                Document(id=7101, title="Processed A", created="2026-02-01T00:00:00+00:00", correspondent_id=7001),
                Document(id=7102, title="Pending A", created="2026-02-02T00:00:00+00:00", correspondent_id=7001),
                Document(id=7103, title="Processed B", created="2026-02-03T00:00:00+00:00", correspondent_id=7002),
                Document(id=7104, title="Unassigned pending", created="2026-02-04T00:00:00+00:00"),
            ]
        )
        db.add_all(
            [
                DocumentEmbedding(doc_id=7101, embedding_source="paperless", chunk_count=1),
                DocumentEmbedding(doc_id=7103, embedding_source="paperless", chunk_count=1),
                DocumentPageText(doc_id=7101, page=1, source="vision_ocr", text="a", raw_text="a", clean_text="a"),
                DocumentPageText(doc_id=7103, page=1, source="vision_ocr", text="b", raw_text="b", clean_text="b"),
                DocumentSuggestion(
                    doc_id=7101,
                    source="paperless_ocr",
                    payload="{}",
                    created_at="2026-02-01T00:00:00+00:00",
                    processed_at="2026-02-01T00:00:00+00:00",
                ),
                DocumentSuggestion(
                    doc_id=7103,
                    source="paperless_ocr",
                    payload="{}",
                    created_at="2026-02-03T00:00:00+00:00",
                    processed_at="2026-02-03T00:00:00+00:00",
                ),
            ]
        )
        db.commit()

    response = api_client.get("/documents/dashboard")
    assert response.status_code == 200
    payload = response.json()

    assert payload["stats"]["total"] == 4
    assert payload["stats"]["embeddings"] == 2
    assert payload["stats"]["fully_processed"] == 2
    assert payload["stats"]["unprocessed"] == 2
    correspondents = {row["name"]: row["count"] for row in payload["correspondents"]}
    assert correspondents["Alpha"] == 2
    assert correspondents["Beta"] == 1
    assert correspondents["Unassigned correspondent"] == 1

    unprocessed = {row["name"]: row["count"] for row in payload["unprocessed_by_correspondent"]}
    assert unprocessed["Alpha"] == 1
    assert unprocessed["Unassigned correspondent"] == 1
    assert "Beta" not in unprocessed
    page_counts = {row["label"]: row["count"] for row in payload["page_counts"]}
    assert page_counts["Unknown"] == 4


def test_process_missing_queue_disabled(api_client: Any) -> None:
    response = api_client.post("/documents/process-missing", params={"dry_run": True})
    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is False
    assert payload["dry_run"] is True


def test_process_missing_rejects_invalid_embeddings_mode(api_client: Any, monkeypatch: Any) -> None:
    from app.routes import documents_actions

    monkeypatch.setattr(documents_actions, "require_queue_enabled", lambda _settings: True)
    response = api_client.post(
        "/documents/process-missing",
        params={"embeddings_mode": "invalid"},
    )
    assert response.status_code == 400
    assert "Invalid embeddings_mode" in str(response.json().get("detail"))


def test_process_missing_rejects_invalid_limit(api_client: Any, monkeypatch: Any) -> None:
    from app.routes import documents_actions

    monkeypatch.setattr(documents_actions, "require_queue_enabled", lambda _settings: True)
    response = api_client.post("/documents/process-missing", params={"limit": 0})
    assert response.status_code == 400
    assert "limit must be >= 1" in str(response.json().get("detail"))


def test_get_document_suggestions_empty(api_client: Any, monkeypatch: Any) -> None:
    from app.services.integrations import meta_cache, paperless

    monkeypatch.setattr(paperless, "get_document", lambda *args, **kwargs: {"content": ""})
    monkeypatch.setattr(meta_cache, "get_cached_tags", lambda *args, **kwargs: [])
    monkeypatch.setattr(meta_cache, "get_cached_correspondents", lambda *args, **kwargs: [])

    response = api_client.get("/documents/123/suggestions")
    assert response.status_code == 200
    payload = response.json()
    assert payload["doc_id"] == 123
    assert payload["suggestions"] == {}
    assert payload["suggestions_meta"] == {}


def test_cleanup_texts_queue_disabled(api_client: Any) -> None:
    response = api_client.post(
        "/documents/cleanup-texts",
        json={"enqueue": True, "clear_first": True},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["queued"] is False
    assert payload["enqueued"] == 0


def test_cleanup_texts_rejects_invalid_source(api_client: Any) -> None:
    response = api_client.post(
        "/documents/cleanup-texts",
        json={"enqueue": False, "source": "invalid_source"},
    )
    assert response.status_code == 400
    assert "Invalid source" in str(response.json().get("detail"))


def test_enqueue_document_task_rejects_invalid_task(api_client: Any) -> None:
    response = api_client.post(
        "/documents/1/operations/enqueue-task",
        json={"task": "invalid_task"},
    )
    assert response.status_code == 400
    assert "Invalid task" in str(response.json().get("detail"))


def test_enqueue_document_task_queue_disabled(api_client: Any) -> None:
    response = api_client.post(
        "/documents/1/operations/enqueue-task",
        json={"task": "sync"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is False
    assert payload["enqueued"] == 0
    assert payload["task"] == "sync"
    assert payload["doc_id"] == 1


def test_list_documents_review_status_unreviewed(api_client: Any, monkeypatch: Any) -> None:
    from app.services.integrations import paperless

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


def test_mark_reviewed_moves_document_out_of_unreviewed(api_client: Any, monkeypatch: Any) -> None:
    from app.services.integrations import paperless

    _insert_local_document(doc_id=41, title="Doc 41", created="2026-02-10T10:00:00+00:00")
    monkeypatch.setattr(
        paperless,
        "list_documents",
        lambda *args, **kwargs: {
            "count": 1,
            "next": None,
            "previous": None,
            "results": [
                {"id": 41, "title": "Doc 41", "modified": "2026-02-10T10:00:00+00:00", "tags": []},
            ],
        },
    )

    before = api_client.get("/documents", params={"include_derived": True, "review_status": "unreviewed"})
    assert before.status_code == 200
    assert before.json()["count"] == 1

    marked = api_client.post("/documents/41/review/mark")
    assert marked.status_code == 200
    marked_payload = marked.json()
    assert marked_payload["status"] == "ok"
    assert marked_payload["doc_id"] == 41
    assert isinstance(marked_payload["reviewed_at"], str)
    assert marked_payload["reviewed_at"]

    after = api_client.get("/documents", params={"include_derived": True, "review_status": "unreviewed"})
    assert after.status_code == 200
    assert after.json()["count"] == 0


def test_mark_reviewed_updates_local_review_status(api_client: Any, monkeypatch: Any) -> None:
    from app.services.integrations import paperless

    _insert_local_document(doc_id=45, title="Doc 45", created="2026-02-10T10:00:00+00:00")
    monkeypatch.setattr(
        paperless,
        "get_document_cached",
        lambda *args, **kwargs: {
            "id": 45,
            "title": "Doc 45",
            "created": "2026-02-10T10:00:00+00:00",
            "modified": "2026-02-10T10:00:00+00:00",
            "correspondent": None,
            "tags": [],
            "notes": [],
        },
    )

    before = api_client.get("/documents/45/local")
    assert before.status_code == 200
    before_payload = before.json()
    assert before_payload["review_status"] == "unreviewed"
    assert before_payload["reviewed_at"] is None

    marked = api_client.post("/documents/45/review/mark")
    assert marked.status_code == 200
    assert marked.json()["status"] == "ok"

    after = api_client.get("/documents/45/local")
    assert after.status_code == 200
    after_payload = after.json()
    assert after_payload["review_status"] == "reviewed"
    assert isinstance(after_payload["reviewed_at"], str)
    assert after_payload["reviewed_at"]


def test_mark_reviewed_returns_missing_when_document_not_local(api_client: Any) -> None:
    response = api_client.post("/documents/9999/review/mark")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "missing"
    assert payload["doc_id"] == 9999
    assert payload["reviewed_at"] is None


def test_list_documents_review_status_needs_review(api_client: Any, monkeypatch: Any) -> None:
    from app.services.integrations import paperless

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


def test_list_documents_local_overrides_force_needs_review(
    api_client: Any, monkeypatch: Any
) -> None:
    from app.services.integrations import paperless

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


def test_pending_new_tags_force_needs_review(api_client: Any, monkeypatch: Any) -> None:
    from app.services.integrations import paperless

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


def test_list_documents_filter_without_correspondent(api_client: Any, monkeypatch: Any) -> None:
    from app.services.integrations import paperless

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


def test_document_pipeline_fanout_returns_ordered_items(api_client: Any, monkeypatch: Any) -> None:
    from app.services.integrations import paperless

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


def test_document_pipeline_fanout_rejects_invalid_embeddings_mode(api_client: Any) -> None:
    _insert_local_document(doc_id=22, title="Fanout Invalid Mode", created="2026-02-10T10:00:00+00:00")
    response = api_client.get(
        "/documents/22/pipeline-fanout",
        params={"embeddings_mode": "invalid"},
    )
    assert response.status_code == 400
    assert "Invalid embeddings_mode" in str(response.json().get("detail"))


def test_continue_document_pipeline_rejects_invalid_embeddings_mode(api_client: Any) -> None:
    _insert_local_document(doc_id=23, title="Continue Invalid Mode", created="2026-02-10T10:00:00+00:00")
    response = api_client.post(
        "/documents/23/pipeline/continue",
        params={"embeddings_mode": "invalid"},
    )
    assert response.status_code == 400
    assert "Invalid embeddings_mode" in str(response.json().get("detail"))


def test_continue_document_pipeline_queue_disabled(api_client: Any) -> None:
    _insert_local_document(doc_id=24, title="Continue Queue Disabled", created="2026-02-10T10:00:00+00:00")
    response = api_client.post("/documents/24/pipeline/continue", params={"dry_run": True})
    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is False
    assert payload["doc_id"] == 24
    assert payload["dry_run"] is True
    assert payload["missing_tasks"] == 0
    assert payload["enqueued"] == 0


def _insert_local_note(doc_id: int, note: str, note_id: int = -1) -> None:
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


def test_pipeline_status_ignores_metadata_only_modified_for_processing(
    api_client: Any, monkeypatch: Any
) -> None:
    from app.services.integrations import paperless

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
        db.add(
            TaskRun(
                doc_id=31,
                task="similarity_index",
                source=None,
                status="completed",
                worker_id="worker:test",
                attempt=1,
                started_at="2026-02-10T10:06:30+00:00",
                finished_at="2026-02-10T10:06:35+00:00",
                created_at="2026-02-10T10:06:30+00:00",
                updated_at="2026-02-10T10:06:35+00:00",
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


def test_pipeline_status_marks_evidence_optional_for_no_text_layer(
    api_client: Any, monkeypatch: Any
) -> None:
    from app.services.integrations import paperless

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


def test_reset_and_reprocess_clears_doc_task_runs(api_client: Any, monkeypatch: Any) -> None:
    from app.routes import documents_actions
    from app.services.integrations import paperless

    _insert_local_document(doc_id=67, title="Reset TaskRuns", created="2026-02-10T10:00:00+00:00")
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(
            TaskRun(
                doc_id=67,
                task="embeddings_vision",
                source=None,
                status="completed",
                worker_id="worker:test",
                attempt=1,
                started_at="2026-02-20T09:16:44+00:00",
                finished_at="2026-02-20T09:17:16+00:00",
                created_at="2026-02-20T09:16:44+00:00",
                updated_at="2026-02-20T09:17:16+00:00",
            )
        )
        db.commit()

    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda *_args, **_kwargs: {
            "id": 67,
            "title": "Reset TaskRuns",
            "created": "2026-02-10T10:00:00+00:00",
            "modified": "2026-02-10T10:00:00+00:00",
            "content": "example",
            "tags": [],
            "correspondent": None,
            "document_type": None,
            "document_date": "2026-02-10",
        },
    )
    monkeypatch.setattr(documents_actions, "require_queue_enabled", lambda _settings: False)

    response = api_client.post("/documents/67/operations/reset-and-reprocess")
    assert response.status_code == 200
    payload = response.json()
    assert payload["reset"] is True

    with Session(engine) as db:
        assert db.query(TaskRun).filter(TaskRun.doc_id == 67).count() == 0


def test_delete_similarity_index_clears_similarity_task_runs(
    api_client: Any, monkeypatch: Any
) -> None:
    from app.routes import documents_actions

    _insert_local_document(doc_id=77, title="Similarity Reset", created="2026-02-10T10:00:00+00:00")
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(
            TaskRun(
                doc_id=77,
                task="similarity_index",
                source=None,
                status="completed",
                worker_id="worker:test",
                attempt=1,
                started_at="2026-02-20T09:16:44+00:00",
                finished_at="2026-02-20T09:17:16+00:00",
                created_at="2026-02-20T09:16:44+00:00",
                updated_at="2026-02-20T09:17:16+00:00",
            )
        )
        db.add(
            TaskRun(
                doc_id=77,
                task="embeddings_vision",
                source=None,
                status="completed",
                worker_id="worker:test",
                attempt=1,
                started_at="2026-02-20T09:16:00+00:00",
                finished_at="2026-02-20T09:16:30+00:00",
                created_at="2026-02-20T09:16:00+00:00",
                updated_at="2026-02-20T09:16:30+00:00",
            )
        )
        db.commit()

    monkeypatch.setattr(documents_actions, "delete_similarity_points", lambda *_args, **_kwargs: None)

    response = api_client.post("/documents/delete/similarity-index")
    assert response.status_code == 200
    payload = response.json()
    assert payload["qdrant_deleted"] == 1
    assert payload["qdrant_errors"] == 0
    assert payload["deleted"] >= 1

    with Session(engine) as db:
        assert db.query(TaskRun).filter(TaskRun.doc_id == 77, TaskRun.task == "similarity_index").count() == 0
        assert db.query(TaskRun).filter(TaskRun.doc_id == 77, TaskRun.task == "embeddings_vision").count() == 1


def test_get_local_document_note_override_sets_needs_review(
    api_client: Any, monkeypatch: Any
) -> None:
    from app.services.integrations import paperless

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


def test_list_documents_detects_correspondent_clear_as_override(
    api_client: Any, monkeypatch: Any
) -> None:
    from app.services.integrations import paperless

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


def test_get_local_document_detects_empty_title_as_override(
    api_client: Any, monkeypatch: Any
) -> None:
    from app.services.integrations import paperless

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


def test_list_documents_summary_preview_only_when_requested(
    api_client: Any, monkeypatch: Any
) -> None:
    from app.services.integrations import paperless

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


def test_list_documents_includes_local_analysis_fields(api_client: Any, monkeypatch: Any) -> None:
    from app.services.integrations import paperless

    _insert_local_document(
        doc_id=45,
        title="Doc 45",
        created="2026-02-10T10:00:00+00:00",
        analysis_model="gpt-local",
        analysis_processed_at="2026-02-11T12:30:00+00:00",
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
                    "id": 45,
                    "title": "Doc 45",
                    "created": "2026-02-10T10:00:00+00:00",
                    "modified": "2026-02-10T10:00:00+00:00",
                    "correspondent": None,
                    "tags": [],
                },
            ],
        },
    )

    response = api_client.get("/documents", params={"include_derived": True})
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["results"][0]["analysis_model"] == "gpt-local"
    assert payload["results"][0]["analysis_processed_at"] == "2026-02-11T12:30:00+00:00"


def test_list_documents_includes_suggestion_and_vision_flags(
    api_client: Any, monkeypatch: Any
) -> None:
    from app.services.integrations import paperless

    _insert_local_document(
        doc_id=46,
        title="Doc 46",
        created="2026-02-10T10:00:00+00:00",
    )
    _insert_suggestion(doc_id=46, source="paperless_ocr", payload='{"title":"Doc 46"}')
    _insert_suggestion(doc_id=46, source="vision_ocr", payload='{"title":"Doc 46 Vision"}')
    _insert_page_text(doc_id=46, page=1, source="vision_ocr", text="Vision page 1")
    _insert_page_text(doc_id=46, page=2, source="vision_ocr", text="Vision page 2")
    monkeypatch.setattr(
        paperless,
        "list_documents",
        lambda *args, **kwargs: {
            "count": 1,
            "next": None,
            "previous": None,
            "results": [
                {
                    "id": 46,
                    "title": "Doc 46",
                    "created": "2026-02-10T10:00:00+00:00",
                    "modified": "2026-02-10T10:00:00+00:00",
                    "correspondent": None,
                    "tags": [],
                },
            ],
        },
    )

    response = api_client.get("/documents", params={"include_derived": True})
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    row = payload["results"][0]
    assert row["has_suggestions"] is True
    assert row["has_suggestions_paperless"] is True
    assert row["has_suggestions_vision"] is True
    assert row["has_vision_pages"] is True
