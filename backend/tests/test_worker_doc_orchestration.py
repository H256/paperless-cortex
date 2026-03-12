from __future__ import annotations

from typing import Any

from app.config import load_settings
from app.models import Document
from app.worker import _process_doc


def test_process_doc_large_document_with_vision_runs_expected_flow(
    session_factory: Any, monkeypatch: Any
) -> None:
    from app import worker as worker_mod

    settings = load_settings()
    calls: list[tuple[object, ...]] = []

    class FakePage:
        def __init__(self, page: int, text: str, source: str) -> None:
            self.page = page
            self.text = text
            self.source = source

    with session_factory() as db:
        db.add(Document(id=704, title="Doc 704", content="paperless content", page_count=3))
        db.commit()

        monkeypatch.setattr(worker_mod, "is_cancel_requested", lambda *_args, **_kwargs: False)
        monkeypatch.setattr(worker_mod, "_process_sync_only", lambda *_args, **_kwargs: calls.append(("sync", 704)))
        monkeypatch.setattr(
            worker_mod.paperless,
            "get_document",
            lambda *_args, **_kwargs: {"id": 704, "title": "Remote 704"},
        )
        monkeypatch.setattr(worker_mod, "get_document_or_none", lambda *_args, **_kwargs: db.get(Document, 704))
        monkeypatch.setattr(
            worker_mod,
            "_process_evidence_index",
            lambda *_args, **kwargs: calls.append(("evidence", kwargs.get("run_id"))),
        )
        monkeypatch.setattr(
            worker_mod,
            "ensure_document_ocr_score",
            lambda _settings, _db, _doc, source, **_kwargs: calls.append(("score", source)),
        )
        monkeypatch.setattr(
            worker_mod,
            "collect_page_texts",
            lambda *_args, **_kwargs: (
                [FakePage(1, "paperless page", "paperless_ocr")],
                [FakePage(1, "vision page", "vision_ocr")],
                [],
            ),
        )
        monkeypatch.setattr(
            worker_mod,
            "_embed_with_pages",
            lambda _settings, _db, _doc, baseline_pages, vision_pages, source, **kwargs: calls.append(
                ("embed", source, len(baseline_pages), len(vision_pages), kwargs.get("run_id"))
            ),
        )
        monkeypatch.setattr(worker_mod, "_is_large_doc", lambda *_args, **_kwargs: True)
        monkeypatch.setattr(
            worker_mod,
            "_process_page_notes",
            lambda _settings, _db, _doc_id, source, **kwargs: calls.append(
                ("page_notes", source, kwargs.get("run_id"))
            ),
        )
        monkeypatch.setattr(
            worker_mod,
            "_process_summary_hierarchical",
            lambda _settings, _db, _doc_id, source, **kwargs: calls.append(
                ("summary", source, kwargs.get("run_id"))
            ),
        )
        monkeypatch.setattr(worker_mod, "get_cached_tags", lambda *_args, **_kwargs: ["tag-a"])
        monkeypatch.setattr(
            worker_mod, "get_cached_correspondents", lambda *_args, **_kwargs: ["corr-a"]
        )
        monkeypatch.setattr(
            worker_mod,
            "_service_build_distilled_context_from_hier_summary",
            lambda _db, **kwargs: (
                "paperless summary"
                if kwargs.get("source") == "paperless_ocr"
                else "vision summary"
            ),
        )
        monkeypatch.setattr(
            worker_mod,
            "_service_build_distilled_context_from_page_notes",
            lambda *_args, **_kwargs: "",
        )
        monkeypatch.setattr(
            worker_mod,
            "_service_join_page_texts_limited",
            lambda *_args, **_kwargs: "joined vision text",
        )

        generated_payloads: list[tuple[str, str]] = []

        def fake_generate(
            _settings: Any, raw: dict[str, object], text: str, **_kwargs: Any
        ) -> dict[str, str]:
            generated_payloads.append((str(raw.get("title")), text))
            return {"title": text}

        persisted: list[tuple[int, str, dict[str, str]]] = []

        def fake_persist(
            _db: Any, doc_id: int, source: str, payload: dict[str, str], **_kwargs: Any
        ) -> None:
            persisted.append((doc_id, source, payload))

        monkeypatch.setattr(worker_mod, "generate_normalized_suggestions", fake_generate)
        monkeypatch.setattr(worker_mod, "persist_suggestions", fake_persist)

        _process_doc(settings, db, 704, run_id=77)

    assert calls == [
        ("sync", 704),
        ("evidence", 77),
        ("score", "paperless_ocr"),
        ("score", "vision_ocr"),
        ("embed", "vision", 1, 1, 77),
        ("page_notes", "paperless_ocr", 77),
        ("page_notes", "vision_ocr", 77),
        ("summary", "vision_ocr", 77),
    ]
    assert generated_payloads == [
        ("Remote 704", "paperless summary"),
        ("Remote 704", "vision summary"),
    ]
    assert persisted == [
        (704, "paperless_ocr", {"title": "paperless summary"}),
        (704, "vision_ocr", {"title": "vision summary"}),
    ]


def test_process_doc_aborts_early_when_cancel_requested(
    session_factory: Any, monkeypatch: Any
) -> None:
    from app import worker as worker_mod

    settings = load_settings()
    called = {"sync": 0}

    with session_factory() as db:
        monkeypatch.setattr(worker_mod, "is_cancel_requested", lambda *_args, **_kwargs: True)
        monkeypatch.setattr(
            worker_mod,
            "_process_sync_only",
            lambda *_args, **_kwargs: called.__setitem__("sync", called["sync"] + 1),
        )

        _process_doc(settings, db, 999, run_id=5)

    assert called["sync"] == 0
