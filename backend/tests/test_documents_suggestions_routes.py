from __future__ import annotations

import json
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Document, DocumentSuggestion


def test_suggest_field_note_uses_current_summary(api_client, monkeypatch):
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
        settings,
        document,
        text,
        tags,
        correspondents,
        field,
        count,
        current_value=None,
    ):
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


def test_apply_field_note_updates_summary_payload(api_client):
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
