from __future__ import annotations

from typing import Any

from app.models import Document
from app.services.ai.chat import _parse_date, _sort_sources_chrono


def test_parse_date_normalizes_naive_to_aware() -> None:
    naive = _parse_date("2026-01-01")
    aware = _parse_date("2026-01-01T10:00:00+00:00")
    assert naive is not None
    assert aware is not None
    assert naive.tzinfo is not None
    # Both must be directly comparable (the original bug: naive vs aware raised TypeError).
    assert naive < aware or naive > aware
    assert _parse_date(None) is None
    assert _parse_date("not-a-date") is None


def test_sort_sources_chrono_mixed_naive_aware_no_typeerror(session_factory: Any) -> None:
    session = session_factory()
    try:
        # Doc 1: only a naive document_date (String column, e.g. '2026-01-01').
        session.add(
            Document(
                id=1,
                title="Doc 1",
                document_date="2026-01-01",
                created=None,
            )
        )
        # Doc 2: only an aware created timestamp (utc_now_iso format).
        session.add(
            Document(
                id=2,
                title="Doc 2",
                document_date=None,
                created="2026-03-01T00:00:00+00:00",
            )
        )
        session.commit()

        sources = [
            {"doc_id": 2, "page": 1, "source": "vision_ocr", "text": "later"},
            {"doc_id": 1, "page": 1, "source": "vision_ocr", "text": "earlier"},
        ]

        # Before the fix this raised:
        #   TypeError: can't compare offset-naive and offset-aware datetimes
        ordered = _sort_sources_chrono(sources, db=session)

        assert [s["doc_id"] for s in ordered] == [1, 2]
    finally:
        session.close()
