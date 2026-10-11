from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.models import Document, DocumentPageText
from app.services.ai.page_selection import PageSelectionError, parse_page_spec, select_page_text
from app.services.ai.suggestion_operations import generate_field_variants_payload


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        (None, None),
        ("", None),
        ("  ", None),
        ("1", [1]),
        ("1-3", [1, 2, 3]),
        ("3, 1-2 ,3", [1, 2, 3]),
        ("5,2", [2, 5]),
    ],
)
def test_parse_page_spec(spec: str | None, expected: list[int] | None) -> None:
    assert parse_page_spec(spec) == expected


@pytest.mark.parametrize("spec", ["0", "a", "1-", "-2", "3-1", "1,,2", "1-9999", "1" * 200])
def test_parse_page_spec_rejects_malformed_input(spec: str) -> None:
    with pytest.raises(PageSelectionError):
        parse_page_spec(spec)


@pytest.fixture
def db(session_factory: Any) -> Any:
    with session_factory() as session:
        yield session


def test_select_page_text_uses_stored_pages_in_page_order(db: Any) -> None:
    db.add(Document(id=1, title="d", content="ignored"))
    db.add(DocumentPageText(doc_id=1, page=2, source="vision_ocr", text="B"))
    db.add(DocumentPageText(doc_id=1, page=1, source="vision_ocr", text="A"))
    db.add(DocumentPageText(doc_id=1, page=1, source="paperless_ocr", text="OTHER"))
    db.commit()

    text = select_page_text(db, doc_id=1, source="vision_ocr", pages=[1, 2], content=None)

    assert text == "A\n\nB"


def test_select_page_text_falls_back_to_form_feed_split_for_paperless_ocr(db: Any) -> None:
    db.add(Document(id=2, title="d", content="x"))
    db.commit()

    text = select_page_text(
        db, doc_id=2, source="paperless_ocr", pages=[2], content="one\ftwo\fthree"
    )

    assert text == "two"


def test_select_page_text_never_falls_back_to_the_whole_text(db: Any) -> None:
    db.add(Document(id=3, title="d", content="single page"))
    db.add(DocumentPageText(doc_id=3, page=1, source="vision_ocr", text="A"))
    db.commit()

    with pytest.raises(PageSelectionError, match="no page structure"):
        select_page_text(db, doc_id=3, source="paperless_ocr", pages=[1], content="single page")
    with pytest.raises(PageSelectionError, match="None of the requested pages"):
        select_page_text(db, doc_id=3, source="vision_ocr", pages=[4], content=None)


def test_queued_suggest_field_task_carries_the_resolved_pages(db: Any) -> None:
    db.add(Document(id=4, title="d", content="x"))
    db.add(DocumentPageText(doc_id=4, page=1, source="vision_ocr", text="A"))
    db.add(DocumentPageText(doc_id=4, page=2, source="vision_ocr", text="B"))
    db.commit()
    enqueued: list[dict[str, object]] = []

    result = generate_field_variants_payload(
        doc_id=4,
        source="vision_ocr",
        field="title",
        count=1,
        priority=False,
        settings=SimpleNamespace(queue_enabled=True, enable_vision_ocr=False),  # type: ignore[arg-type]
        db=db,
        get_document_fn=lambda _s, did: {"id": did, "content": "x"},
        get_cached_tags_fn=lambda _s: [],
        get_cached_correspondents_fn=lambda _s: [],
        get_document_or_none_fn=lambda _db, _id: None,
        pages="2",
        get_page_text_layers_fn=lambda *_a, **_k: ([], []),
        fetch_pdf_bytes_fn=lambda: b"",
        upsert_page_texts_fn=lambda *_a, **_k: None,
        ensure_document_ocr_score_fn=lambda *_a, **_k: None,
        generate_field_variants_fn=lambda *_a, **_k: {"variants": []},
        enqueue_task_front_fn=lambda _s, task: enqueued.append(task) or 1,
    )

    assert result["queued"] is True
    assert enqueued[0]["pages"] == [2]


def test_queued_suggest_field_task_rejects_bad_pages_before_enqueue(db: Any) -> None:
    db.add(Document(id=5, title="d", content="x"))
    db.commit()
    enqueued: list[dict[str, object]] = []

    with pytest.raises(PageSelectionError):
        generate_field_variants_payload(
            doc_id=5,
            source="paperless_ocr",
            field="title",
            count=1,
            priority=False,
            settings=SimpleNamespace(queue_enabled=True, enable_vision_ocr=False),  # type: ignore[arg-type]
            db=db,
            get_document_fn=lambda _s, did: {"id": did, "content": "x"},
            get_cached_tags_fn=lambda _s: [],
            get_cached_correspondents_fn=lambda _s: [],
            get_document_or_none_fn=lambda _db, _id: None,
            pages="1",
            get_page_text_layers_fn=lambda *_a, **_k: ([], []),
            fetch_pdf_bytes_fn=lambda: b"",
            upsert_page_texts_fn=lambda *_a, **_k: None,
            ensure_document_ocr_score_fn=lambda *_a, **_k: None,
            generate_field_variants_fn=lambda *_a, **_k: {"variants": []},
            enqueue_task_front_fn=lambda _s, task: enqueued.append(task) or 1,
        )

    assert enqueued == []
