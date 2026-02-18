from __future__ import annotations

from app.config import load_settings
from app.models import Document, DocumentPageText
from app.worker import _process_suggestions_vision


def test_process_suggestions_vision_backfills_missing_pages(session_factory, monkeypatch):
    from app import worker as worker_mod

    monkeypatch.setenv("ENABLE_VISION_OCR", "1")
    settings = load_settings()
    captured: dict[str, object] = {}

    with session_factory() as db:
        db.add(Document(id=701, title="Doc 701", content="content", page_count=1))
        db.commit()

        monkeypatch.setattr(worker_mod.paperless, "get_document", lambda *_args, **_kwargs: {"id": 701})
        monkeypatch.setattr(worker_mod, "get_cached_tags", lambda *_args, **_kwargs: [])
        monkeypatch.setattr(worker_mod, "get_cached_correspondents", lambda *_args, **_kwargs: [])

        def fake_generate(_settings, _document, text, **_kwargs):
            captured["text"] = text
            return {"title": "Vision Title"}

        def fake_persist(_db, doc_id, source, payload, **_kwargs):
            captured["persist"] = (doc_id, source, payload)

        def fake_vision_ocr_only(_settings, db_session, doc_id, force=False, run_id=None):
            assert force is False
            assert run_id is None
            db_session.add(
                DocumentPageText(
                    doc_id=doc_id,
                    page=1,
                    source="vision_ocr",
                    text="Recovered vision OCR text",
                )
            )
            db_session.commit()

        monkeypatch.setattr(worker_mod, "generate_normalized_suggestions", fake_generate)
        monkeypatch.setattr(worker_mod, "persist_suggestions", fake_persist)
        monkeypatch.setattr(worker_mod, "_process_vision_ocr_only", fake_vision_ocr_only)

        _process_suggestions_vision(settings, db, 701)

    assert "Recovered vision OCR text" in str(captured.get("text", ""))
    assert captured.get("persist") == (701, "vision_ocr", {"title": "Vision Title"})


def test_process_suggestions_vision_raises_when_no_pages_available(session_factory, monkeypatch):
    from app import worker as worker_mod

    monkeypatch.setenv("ENABLE_VISION_OCR", "1")
    settings = load_settings()

    with session_factory() as db:
        db.add(Document(id=702, title="Doc 702", content="content", page_count=1))
        db.commit()

        monkeypatch.setattr(worker_mod.paperless, "get_document", lambda *_args, **_kwargs: {"id": 702})
        monkeypatch.setattr(worker_mod, "get_cached_tags", lambda *_args, **_kwargs: [])
        monkeypatch.setattr(worker_mod, "get_cached_correspondents", lambda *_args, **_kwargs: [])
        monkeypatch.setattr(worker_mod, "_process_vision_ocr_only", lambda *_args, **_kwargs: None)

        try:
            _process_suggestions_vision(settings, db, 702)
            assert False, "Expected RuntimeError for missing vision pages"
        except RuntimeError as exc:
            assert "vision_suggestions_missing_pages" in str(exc)
