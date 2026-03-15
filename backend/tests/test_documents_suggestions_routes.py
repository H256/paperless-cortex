from __future__ import annotations

import json
import os
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Document, DocumentSuggestion, SuggestionAudit


def test_suggest_field_note_uses_current_summary(api_client: Any, monkeypatch: Any) -> None:
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(Document(id=707, title="Doc 707", content="Inhalt"))
        db.add(
            DocumentSuggestion(
                doc_id=707,
                source="paperless_ocr",
                payload=json.dumps({"summary": "old summary"}, ensure_ascii=False),
            )
        )
        db.commit()

    from app.routes import documents_suggestions as route_mod
    from app.services.integrations import paperless

    captured: dict[str, object] = {}

    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda settings, doc_id: {"id": doc_id, "title": "Remote", "content": "text"},
    )
    monkeypatch.setattr(route_mod, "get_cached_tags", lambda settings: [])
    monkeypatch.setattr(route_mod, "get_cached_correspondents", lambda settings: [])

    def _fake_generate_field_variants(
        settings: Any,
        document: Any,
        text: str,
        tags: Any,
        correspondents: Any,
        field: str,
        count: int,
        current_value: object = None,
    ) -> dict[str, list[str] | object]:
        captured["field"] = field
        captured["current_value"] = current_value
        return {"variants": ["new summary variant"]}

    monkeypatch.setattr(route_mod, "generate_field_variants", _fake_generate_field_variants)

    response = api_client.post(
        "/documents/707/suggestions/field?priority=true",
        json={"source": "paperless_ocr", "field": "note", "count": 1},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["variants"] == ["new summary variant"]
    assert captured["field"] == "note"
    assert captured["current_value"] == "old summary"


def test_apply_field_note_updates_summary_payload(api_client: Any) -> None:
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(Document(id=708, title="Doc 708", content="Inhalt"))
        db.add(
            DocumentSuggestion(
                doc_id=708,
                source="vision_ocr",
                payload=json.dumps({"summary": "before"}, ensure_ascii=False),
            )
        )
        db.commit()

    response = api_client.post(
        "/documents/708/suggestions/field/apply",
        json={"source": "vision_ocr", "field": "note", "value": "after"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["suggestions"]["vision_ocr"]["summary"] == "after"


def test_apply_suggestion_title_invalidates_local_detail_and_writeback_candidate_state(
    api_client: Any, monkeypatch: Any
) -> None:
    from app.services.documents import documents_list_cache, local_document_cache
    from app.services.integrations import paperless
    from app.services.writeback.writeback_preview import local_writeback_candidate_doc_ids
    from app.services.writeback.writeback_preview_cache import (
        get_cached_writeback_candidate_doc_ids,
        invalidate_writeback_preview_cache,
    )

    invalidate_writeback_preview_cache()
    documents_list_cache.invalidate_documents_list_cache()
    local_document_cache.invalidate_local_document_cache()

    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(
            Document(
                id=709,
                title="Remote title",
                created="2026-02-20T10:00:00+00:00",
                modified="2026-02-20T10:00:00+00:00",
            )
        )
        db.commit()

    monkeypatch.setattr(
        paperless,
        "get_document_cached",
        lambda _settings, doc_id: {
            "id": doc_id,
            "title": "Remote title",
            "created": "2026-02-20T10:00:00+00:00",
            "modified": "2026-02-20T10:00:00+00:00",
            "correspondent": None,
            "tags": [],
            "notes": [],
        },
    )

    before = api_client.get("/documents/709/local")
    assert before.status_code == 200
    assert before.json()["local_overrides"] is False

    with Session(engine) as db:
        cached_candidates = get_cached_writeback_candidate_doc_ids(
            build_candidates=lambda: local_writeback_candidate_doc_ids(db)
        )
        assert 709 not in cached_candidates

    response = api_client.post(
        "/documents/709/apply-suggestion",
        json={"source": "paperless_ocr", "field": "title", "value": "Local changed title"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    after = api_client.get("/documents/709/local")
    assert after.status_code == 200
    after_payload = after.json()
    assert after_payload["title"] == "Local changed title"
    assert after_payload["local_overrides"] is True
    assert after_payload["review_status"] == "needs_review"

    with Session(engine) as db:
        refreshed_candidates = get_cached_writeback_candidate_doc_ids(
            build_candidates=lambda: local_writeback_candidate_doc_ids(db)
        )
        assert 709 in refreshed_candidates
        audit = (
            db.query(SuggestionAudit)
            .filter(
                SuggestionAudit.doc_id == 709,
                SuggestionAudit.action == "apply_to_document:title",
            )
            .one_or_none()
        )
        assert audit is not None
