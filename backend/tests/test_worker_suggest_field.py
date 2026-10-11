from __future__ import annotations

import json
from typing import Any

from app.config import load_settings
from app.models import Document, DocumentPageText
from app.worker import _process_suggest_field


def test_process_suggest_field_uses_vision_pages_and_persists_variants(
    session_factory: Any, monkeypatch: Any
) -> None:
    from app import worker as worker_mod

    settings = load_settings()
    captured: dict[str, object] = {}

    with session_factory() as db:
        db.add(Document(id=703, title="Doc 703", content="paperless text", page_count=2))
        db.add(
            DocumentPageText(
                doc_id=703,
                page=1,
                source="vision_ocr",
                text="Vision page one",
            )
        )
        db.add(
            DocumentPageText(
                doc_id=703,
                page=2,
                source="vision_ocr",
                text="Vision page two",
            )
        )
        db.commit()

        monkeypatch.setattr(worker_mod.paperless, "get_document", lambda *_args, **_kwargs: {"id": 703})
        monkeypatch.setattr(worker_mod, "get_cached_tags", lambda *_args, **_kwargs: [])
        monkeypatch.setattr(worker_mod, "get_cached_correspondents", lambda *_args, **_kwargs: [])

        def fake_generate(
            _settings: Any, _document: Any, text: str, **kwargs: Any
        ) -> dict[str, list[str]]:
            captured["text"] = text
            captured["kwargs"] = kwargs
            return {"variants": ["Alt title 1", "Alt title 2"]}

        def fake_upsert(
            _db: Any,
            doc_id: int,
            source: str,
            payload: str,
            **kwargs: Any,
        ) -> None:
            captured["upsert"] = (doc_id, source, json.loads(payload), kwargs)

        def fake_audit(
            _db: Any, doc_id: int, source: str, action: str, **kwargs: Any
        ) -> None:
            captured["audit"] = (doc_id, source, action, kwargs)

        monkeypatch.setattr(worker_mod, "generate_field_variants", fake_generate)
        monkeypatch.setattr(worker_mod, "upsert_suggestion", fake_upsert)
        monkeypatch.setattr(worker_mod, "audit_suggestion_run", fake_audit)

        _process_suggest_field(
            settings,
            db,
            {
                "doc_id": 703,
                "source": "vision_ocr",
                "field": "title",
                "count": 2,
                "current": "Current title",
            },
        )

    assert "Vision page one" in str(captured.get("text", ""))
    assert "Vision page two" in str(captured.get("text", ""))
    assert captured.get("upsert") == (
        703,
        "vvar:title",
        {"variants": ["Alt title 1", "Alt title 2"]},
        {"model_name": settings.text_model, "commit": False},
    )
    assert captured.get("audit") == (
        703,
        "vision_ocr",
        "field_variants:title",
        {"commit": False},
    )


def test_process_suggest_field_note_is_not_dropped_in_queue_mode(
    session_factory: Any, monkeypatch: Any
) -> None:
    """Regression for routes-001: a queued note/field variant request must be
    processed by the worker, not silently dropped (the inline path generates
    note variants; the worker previously whitelisted only
    title/date/correspondent/tags and early-returned for note)."""
    from app import worker as worker_mod

    settings = load_settings()
    captured: dict[str, object] = {}

    with session_factory() as db:
        db.add(Document(id=708, title="Doc 708", content="paperless note text", page_count=1))
        db.commit()

        monkeypatch.setattr(worker_mod.paperless, "get_document", lambda *_args, **_kwargs: {"id": 708})
        monkeypatch.setattr(worker_mod, "get_cached_tags", lambda *_args, **_kwargs: [])
        monkeypatch.setattr(worker_mod, "get_cached_correspondents", lambda *_args, **_kwargs: [])

        def fake_generate(
            _settings: Any, _document: Any, text: str, **kwargs: Any
        ) -> dict[str, list[str]]:
            captured["text"] = text
            captured["kwargs"] = kwargs
            return {"variants": ["Summary variant 1", "Summary variant 2"]}

        def fake_upsert(
            _db: Any,
            doc_id: int,
            source: str,
            payload: str,
            **kwargs: Any,
        ) -> None:
            captured["upsert"] = (doc_id, source, json.loads(payload), kwargs)

        def fake_audit(
            _db: Any, doc_id: int, source: str, action: str, **kwargs: Any
        ) -> None:
            captured["audit"] = (doc_id, source, action, kwargs)

        monkeypatch.setattr(worker_mod, "generate_field_variants", fake_generate)
        monkeypatch.setattr(worker_mod, "upsert_suggestion", fake_upsert)
        monkeypatch.setattr(worker_mod, "audit_suggestion_run", fake_audit)

        _process_suggest_field(
            settings,
            db,
            {
                "doc_id": 708,
                "source": "paperless_ocr",
                "field": "note",
                "count": 2,
                "current": "Current summary",
            },
        )

    # The worker must have generated and persisted note variants (not dropped).
    assert captured.get("upsert") == (
        708,
        "pvar:note",
        {"variants": ["Summary variant 1", "Summary variant 2"]},
        {"model_name": settings.text_model, "commit": False},
    )
    assert captured.get("audit") == (
        708,
        "paperless_ocr",
        "field_variants:note",
        {"commit": False},
    )


def test_process_suggest_field_forwards_queued_focus_passage_and_hint(
    session_factory: Any, monkeypatch: Any
) -> None:
    from app import worker as worker_mod

    settings = load_settings()
    captured: dict[str, Any] = {}

    with session_factory() as db:
        db.add(Document(id=704, title="Doc 704", content="paperless text", page_count=1))
        db.commit()

        monkeypatch.setattr(worker_mod.paperless, "get_document", lambda *_a, **_k: {"id": 704})
        monkeypatch.setattr(worker_mod, "get_cached_tags", lambda *_a, **_k: [])
        monkeypatch.setattr(worker_mod, "get_cached_correspondents", lambda *_a, **_k: [])

        def fake_generate(_settings: Any, _document: Any, _text: str, **kwargs: Any) -> dict[str, Any]:
            captured.update(kwargs)
            return {"variants": ["2026-09-20"]}

        monkeypatch.setattr(worker_mod, "generate_field_variants", fake_generate)
        monkeypatch.setattr(worker_mod, "upsert_suggestion", lambda *_a, **_k: None)
        monkeypatch.setattr(worker_mod, "audit_suggestion_run", lambda *_a, **_k: None)

        _process_suggest_field(
            settings,
            db,
            {
                "doc_id": 704,
                "source": "paperless_ocr",
                "field": "date",
                "count": 1,
                "focus_text": "Rechnungsdatum: 20.09.2026",
                "hint": "Rechnungsdatum, nicht Lieferdatum",
            },
        )

    assert captured["focus_text"] == "Rechnungsdatum: 20.09.2026"
    assert captured["hint"] == "Rechnungsdatum, nicht Lieferdatum"


def test_process_suggest_field_reads_the_requested_text_source(
    session_factory: Any, monkeypatch: Any
) -> None:
    from app import worker as worker_mod

    settings = load_settings()
    seen: dict[str, str] = {}

    with session_factory() as db:
        db.add(Document(id=705, title="Doc 705", content="PAPERLESS TEXT", page_count=1))
        db.add(DocumentPageText(doc_id=705, page=1, source="vision_ocr", text="VISION TEXT"))
        db.commit()

        monkeypatch.setattr(worker_mod.paperless, "get_document", lambda *_a, **_k: {"id": 705})
        monkeypatch.setattr(worker_mod, "get_cached_tags", lambda *_a, **_k: [])
        monkeypatch.setattr(worker_mod, "get_cached_correspondents", lambda *_a, **_k: [])

        def fake_generate(_settings: Any, _document: Any, text: str, **_kwargs: Any) -> dict[str, Any]:
            seen["text"] = text
            return {"variants": ["x"]}

        monkeypatch.setattr(worker_mod, "generate_field_variants", fake_generate)
        monkeypatch.setattr(worker_mod, "upsert_suggestion", lambda *_a, **_k: None)
        monkeypatch.setattr(worker_mod, "audit_suggestion_run", lambda *_a, **_k: None)

        _process_suggest_field(
            settings,
            db,
            {
                "doc_id": 705,
                "source": "vision_ocr",
                "field": "title",
                "count": 1,
                "text_source": "paperless_ocr",
            },
        )

    assert "PAPERLESS TEXT" in seen["text"]
    assert "VISION TEXT" not in seen["text"]
