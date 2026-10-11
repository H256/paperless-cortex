from __future__ import annotations

import json
import os
from typing import Any

import pytest
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


def test_apply_suggestion_date_rejects_non_iso_date(api_client: Any) -> None:
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(Document(id=710, title="Doc 710", content="Inhalt"))
        db.commit()

    # A hallucinated non-ISO date must be rejected, not stored verbatim.
    response = api_client.post(
        "/documents/710/apply-suggestion",
        json={"source": "paperless_ocr", "field": "date", "value": "January 2026"},
    )
    assert response.status_code == 400
    assert "YYYY-MM-DD" in response.json()["detail"]

    with Session(engine) as db:
        doc = db.get(Document, 710)
        assert doc is not None
        assert doc.document_date is None


def test_apply_suggestion_date_accepts_iso_date(api_client: Any) -> None:
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(Document(id=711, title="Doc 711", content="Inhalt"))
        db.commit()

    response = api_client.post(
        "/documents/711/apply-suggestion",
        json={"source": "paperless_ocr", "field": "date", "value": "2026-01-15"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    with Session(engine) as db:
        doc = db.get(Document, 711)
        assert doc is not None
        assert doc.document_date == "2026-01-15"


def test_apply_suggestion_date_rejects_future_iso_date(api_client: Any) -> None:
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(Document(id=712, title="Doc 712", content="Inhalt"))
        db.commit()

    response = api_client.post(
        "/documents/712/apply-suggestion",
        json={"source": "paperless_ocr", "field": "date", "value": "2026-99-99"},
    )
    assert response.status_code == 400
    assert "YYYY-MM-DD" in response.json()["detail"]


def test_apply_suggestion_date_empty_string_clears_date(api_client: Any) -> None:
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(Document(id=713, title="Doc 713", content="Inhalt", document_date="2026-01-01"))
        db.commit()

    # An empty value clears the date (preserves pre-existing behavior).
    response = api_client.post(
        "/documents/713/apply-suggestion",
        json={"source": "paperless_ocr", "field": "date", "value": ""},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    with Session(engine) as db:
        doc = db.get(Document, 713)
        assert doc is not None
        assert doc.document_date is None


def test_suggest_field_invalid_source_returns_400(api_client: Any) -> None:
    response = api_client.post(
        "/documents/710/suggestions/field",
        json={"source": "not_a_source", "field": "title", "count": 1},
    )
    assert response.status_code == 400
    assert "Invalid source" in response.json()["detail"]


def test_suggest_field_invalid_field_returns_400(api_client: Any) -> None:
    response = api_client.post(
        "/documents/711/suggestions/field",
        json={"source": "paperless_ocr", "field": "not_a_field", "count": 1},
    )
    assert response.status_code == 400
    assert "Invalid field" in response.json()["detail"]


def test_apply_field_invalid_source_returns_400(api_client: Any) -> None:
    response = api_client.post(
        "/documents/712/suggestions/field/apply",
        json={"source": "not_a_source", "field": "title", "value": "v"},
    )
    assert response.status_code == 400
    assert "Invalid source" in response.json()["detail"]


def test_apply_field_invalid_field_returns_400(api_client: Any) -> None:
    response = api_client.post(
        "/documents/713/suggestions/field/apply",
        json={"source": "vision_ocr", "field": "not_a_field", "value": "v"},
    )
    assert response.status_code == 400
    assert "Invalid field" in response.json()["detail"]


def test_apply_suggestion_invalid_field_returns_400(api_client: Any) -> None:
    response = api_client.post(
        "/documents/714/apply-suggestion",
        json={"source": "paperless_ocr", "field": "not_a_field", "value": "v"},
    )
    assert response.status_code == 400
    assert "Invalid field" in response.json()["detail"]


def test_get_suggestions_attaches_implausibility_warnings(api_client: Any, monkeypatch: Any) -> None:
    import datetime

    from app.routes import documents_suggestions as route_mod
    from app.services.integrations import paperless

    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(Document(id=720, title="Doc 720", content="Inhalt"))
        # A future date, a filename-like title, and an unknown correspondent.
        db.add(
            DocumentSuggestion(
                doc_id=720,
                source="paperless_ocr",
                payload=json.dumps(
                    {
                        "date": (datetime.date.today() + datetime.timedelta(days=30)).isoformat(),
                        "title": "scan_2026-01-15.pdf",
                        "correspondent": "Unknown Co",
                        "tags": ["invoice"],
                    },
                    ensure_ascii=False,
                ),
            )
        )
        db.commit()

    monkeypatch.setattr(paperless, "get_document", lambda *a, **k: {"content": ""})
    monkeypatch.setattr(route_mod, "get_cached_tags", lambda settings: [])
    monkeypatch.setattr(route_mod, "get_cached_correspondents", lambda settings: ["Acme"])

    response = api_client.get("/documents/720/suggestions")
    assert response.status_code == 200
    payload = response.json()
    warnings = payload["suggestions"]["paperless_ocr"]["suggestion_warnings"]
    assert len(warnings) == 3
    assert any("in the future" in w for w in warnings)
    assert any("looks like a filename" in w for w in warnings)
    assert any("not a known correspondent" in w for w in warnings)


def test_get_suggestions_plausible_payload_has_no_warnings(api_client: Any, monkeypatch: Any) -> None:
    from app.routes import documents_suggestions as route_mod
    from app.services.integrations import paperless

    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(Document(id=721, title="Doc 721", content="Inhalt"))
        db.add(
            DocumentSuggestion(
                doc_id=721,
                source="paperless_ocr",
                payload=json.dumps(
                    {
                        "date": "2026-01-15",
                        "title": "Invoice from Acme",
                        "correspondent": "Acme",
                        "tags": ["invoice"],
                    },
                    ensure_ascii=False,
                ),
            )
        )
        db.commit()

    monkeypatch.setattr(paperless, "get_document", lambda *a, **k: {"content": ""})
    monkeypatch.setattr(route_mod, "get_cached_tags", lambda settings: [])
    monkeypatch.setattr(route_mod, "get_cached_correspondents", lambda settings: ["Acme"])

    response = api_client.get("/documents/721/suggestions")
    assert response.status_code == 200
    payload = response.json()
    assert payload["suggestions"]["paperless_ocr"]["suggestion_warnings"] == []


def test_suggest_field_passes_focus_passage_and_hint_to_the_generator(
    api_client: Any, monkeypatch: Any
) -> None:
    from app.routes import documents_suggestions as route_mod
    from app.services.integrations import paperless

    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(Document(id=818, title="Doc 818", content="Inhalt"))
        db.commit()

    monkeypatch.setattr(
        paperless, "get_document", lambda settings, doc_id: {"id": doc_id, "content": "text"}
    )
    monkeypatch.setattr(route_mod, "get_cached_tags", lambda settings: [])
    monkeypatch.setattr(route_mod, "get_cached_correspondents", lambda settings: [])
    captured: dict[str, Any] = {}

    def _fake_generate(*_args: Any, **kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"variants": ["2026-09-20"]}

    monkeypatch.setattr(route_mod, "generate_field_variants", _fake_generate)

    response = api_client.post(
        "/documents/818/suggestions/field?priority=true",
        json={
            "source": "paperless_ocr",
            "field": "date",
            "count": 1,
            "focus_text": "Rechnungsdatum: 20.09.2026",
            "hint": "Rechnungsdatum, nicht Lieferdatum",
        },
    )

    assert response.status_code == 200
    assert response.json()["variants"] == ["2026-09-20"]
    assert captured["focus_text"] == "Rechnungsdatum: 20.09.2026"
    assert captured["hint"] == "Rechnungsdatum, nicht Lieferdatum"


def test_suggest_field_without_guidance_keeps_the_generator_call_unchanged(
    api_client: Any, monkeypatch: Any
) -> None:
    from app.routes import documents_suggestions as route_mod
    from app.services.integrations import paperless

    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(Document(id=819, title="Doc 819", content="Inhalt"))
        db.commit()

    monkeypatch.setattr(
        paperless, "get_document", lambda settings, doc_id: {"id": doc_id, "content": "text"}
    )
    monkeypatch.setattr(route_mod, "get_cached_tags", lambda settings: [])
    monkeypatch.setattr(route_mod, "get_cached_correspondents", lambda settings: [])
    captured: dict[str, Any] = {}

    def _fake_generate(*_args: Any, **kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"variants": ["x"]}

    monkeypatch.setattr(route_mod, "generate_field_variants", _fake_generate)

    response = api_client.post(
        "/documents/819/suggestions/field?priority=true",
        json={"source": "paperless_ocr", "field": "title", "count": 1},
    )

    assert response.status_code == 200
    assert "focus_text" not in captured
    assert "hint" not in captured


def test_suggest_field_passes_prior_variants_as_avoid_list(
    api_client: Any, monkeypatch: Any
) -> None:
    from app.routes import documents_suggestions as route_mod
    from app.services.integrations import paperless

    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(Document(id=820, title="Doc 820", content="Inhalt"))
        db.add(
            DocumentSuggestion(
                doc_id=820,
                source="pvar:title",
                payload=json.dumps({"variants": ["Shown A", "Shown B"]}),
            )
        )
        db.commit()

    monkeypatch.setattr(
        paperless, "get_document", lambda settings, doc_id: {"id": doc_id, "content": "text"}
    )
    monkeypatch.setattr(route_mod, "get_cached_tags", lambda settings: [])
    monkeypatch.setattr(route_mod, "get_cached_correspondents", lambda settings: [])
    captured: dict[str, Any] = {}

    def _fake_generate(*_args: Any, **kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"variants": ["New C"]}

    monkeypatch.setattr(route_mod, "generate_field_variants", _fake_generate)

    response = api_client.post(
        "/documents/820/suggestions/field?priority=true",
        json={"source": "paperless_ocr", "field": "title", "count": 1},
    )

    assert response.status_code == 200
    assert response.json()["variants"] == ["New C"]
    assert captured["avoid_variants"] == ["Shown A", "Shown B"]

def test_text_candidates_route_uses_stored_texts_without_side_effects(
    api_client: Any, monkeypatch: Any
) -> None:
    from app.models import DocumentPageText
    from app.routes import documents_suggestions as route_mod

    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(Document(id=808, title="scan", content="ignored because pages exist"))
        db.add(
            DocumentPageText(
                doc_id=808,
                page=1,
                source="vision_ocr",
                text=(
                    "Lautsprecher Teufel GmbH\nBerlin\nRechnungsdatum: 20.09.2026\n"
                    "Zahlbar bis 04.10.2026"
                ),
            )
        )
        db.commit()

    monkeypatch.setattr(
        route_mod,
        "get_cached_correspondents",
        lambda settings: ["Lautsprecher Teufel GmbH", "Hornbach"],
    )

    response = api_client.get("/documents/808/suggestions/candidates")

    assert response.status_code == 200
    payload = response.json()
    assert payload["doc_id"] == 808
    assert payload["dates"][0]["value"] == "2026-09-20"
    assert payload["dates"][0]["label"] == "issue"
    assert payload["dates"][0]["sources"] == ["vision_ocr"]
    assert payload["correspondents"][0]["name"] == "Lautsprecher Teufel GmbH"
    assert payload["correspondents"][0]["known"] is True


def test_text_candidates_route_falls_back_to_document_content(
    api_client: Any, monkeypatch: Any
) -> None:
    from app.routes import documents_suggestions as route_mod

    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(Document(id=809, title="scan", content="Hornbach Baumarkt\nDatum: 01.03.2026"))
        db.commit()
    monkeypatch.setattr(route_mod, "get_cached_correspondents", lambda settings: ["Hornbach Baumarkt"])

    response = api_client.get("/documents/809/suggestions/candidates")

    assert response.status_code == 200
    payload = response.json()
    assert payload["dates"][0]["value"] == "2026-03-01"
    assert payload["dates"][0]["sources"] == ["content"]
    assert payload["correspondents"][0]["name"] == "Hornbach Baumarkt"


def test_text_candidates_route_unknown_document_returns_404(api_client: Any) -> None:
    assert api_client.get("/documents/99999/suggestions/candidates").status_code == 404


def _suggest_field_text_seen_by_model(
    api_client: Any, monkeypatch: Any, doc_id: int, request_extra: dict[str, Any]
) -> str:
    from app.models import DocumentPageText
    from app.routes import documents_suggestions as route_mod
    from app.services.integrations import paperless

    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(Document(id=doc_id, title=f"Doc {doc_id}", content="PAPERLESS TEXT"))
        db.add(
            DocumentPageText(doc_id=doc_id, page=1, source="vision_ocr", text="VISION TEXT")
        )
        db.commit()

    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda settings, did: {"id": did, "content": "PAPERLESS TEXT"},
    )
    monkeypatch.setattr(route_mod, "get_cached_tags", lambda settings: [])
    monkeypatch.setattr(route_mod, "get_cached_correspondents", lambda settings: [])
    seen: dict[str, str] = {}

    def _fake_generate(_settings: Any, _document: Any, text: str, **_kwargs: Any) -> dict[str, Any]:
        seen["text"] = text
        return {"variants": ["x"]}

    monkeypatch.setattr(route_mod, "generate_field_variants", _fake_generate)

    response = api_client.post(
        f"/documents/{doc_id}/suggestions/field?priority=true",
        json={"source": "vision_ocr", "field": "title", "count": 1, **request_extra},
    )
    assert response.status_code == 200
    return seen["text"]


def test_suggest_field_reads_the_requesting_panels_text_by_default(
    api_client: Any, monkeypatch: Any
) -> None:
    text = _suggest_field_text_seen_by_model(api_client, monkeypatch, 820, {})
    assert text == "VISION TEXT"


def test_suggest_field_can_read_the_other_ocr_text(api_client: Any, monkeypatch: Any) -> None:
    text = _suggest_field_text_seen_by_model(
        api_client, monkeypatch, 821, {"text_source": "paperless_ocr"}
    )
    assert text == "PAPERLESS TEXT"


def test_suggest_field_ignores_an_unknown_text_source(api_client: Any, monkeypatch: Any) -> None:
    text = _suggest_field_text_seen_by_model(
        api_client, monkeypatch, 822, {"text_source": "similar_docs"}
    )
    assert text == "VISION TEXT"


def _suggest_field_with_pages(
    api_client: Any, monkeypatch: Any, doc_id: int, request_extra: dict[str, Any]
) -> Any:
    from app.models import DocumentPageText
    from app.routes import documents_suggestions as route_mod
    from app.services.integrations import paperless

    content = "PAPER ONE\fPAPER TWO\fPAPER THREE"
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(Document(id=doc_id, title=f"Doc {doc_id}", content=content))
        for page, text in enumerate(("VISION ONE", "VISION TWO", "VISION THREE"), start=1):
            db.add(DocumentPageText(doc_id=doc_id, page=page, source="vision_ocr", text=text))
        db.commit()

    monkeypatch.setattr(
        paperless, "get_document", lambda settings, did: {"id": did, "content": content}
    )
    monkeypatch.setattr(route_mod, "get_cached_tags", lambda settings: [])
    monkeypatch.setattr(route_mod, "get_cached_correspondents", lambda settings: [])
    seen: dict[str, str] = {}

    def _fake_generate(_settings: Any, _document: Any, text: str, **_kwargs: Any) -> dict[str, Any]:
        seen["text"] = text
        return {"variants": ["x"]}

    monkeypatch.setattr(route_mod, "generate_field_variants", _fake_generate)
    response = api_client.post(
        f"/documents/{doc_id}/suggestions/field?priority=true",
        json={"field": "title", "count": 1, **request_extra},
    )
    response.seen = seen  # type: ignore[attr-defined]
    return response


def test_suggest_field_restricts_vision_text_to_the_requested_pages(
    api_client: Any, monkeypatch: Any
) -> None:
    response = _suggest_field_with_pages(
        api_client, monkeypatch, 830, {"source": "vision_ocr", "pages": "1,3"}
    )
    assert response.status_code == 200
    assert response.seen["text"] == "VISION ONE\n\nVISION THREE"


def test_suggest_field_restricts_paperless_text_to_the_requested_pages(
    api_client: Any, monkeypatch: Any
) -> None:
    response = _suggest_field_with_pages(
        api_client, monkeypatch, 831, {"source": "paperless_ocr", "pages": "2-3"}
    )
    assert response.status_code == 200
    assert response.seen["text"] == "PAPER TWO\n\nPAPER THREE"


def test_suggest_field_page_restriction_uses_the_chosen_text_source(
    api_client: Any, monkeypatch: Any
) -> None:
    response = _suggest_field_with_pages(
        api_client,
        monkeypatch,
        832,
        {"source": "vision_ocr", "text_source": "paperless_ocr", "pages": "1"},
    )
    assert response.status_code == 200
    assert response.seen["text"] == "PAPER ONE"


@pytest.mark.parametrize("pages", ["0", "abc", "3-1", "9"])
def test_suggest_field_rejects_invalid_or_missing_pages(
    api_client: Any, monkeypatch: Any, pages: str
) -> None:
    response = _suggest_field_with_pages(
        api_client, monkeypatch, 833, {"source": "vision_ocr", "pages": pages}
    )
    assert response.status_code == 422
    assert "text" not in response.seen  # type: ignore[attr-defined]

