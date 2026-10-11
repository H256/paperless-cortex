from __future__ import annotations

from app.services.documents.review_summary import summarize_review_rows


def _row(status: str, correspondent: int | None = 1, **extra: object) -> dict[str, object]:
    return {"review_status": status, "correspondent": correspondent, **extra}


def test_summary_counts_by_status() -> None:
    rows = [
        _row("reviewed"),
        _row("reviewed", correspondent=None),
        _row("unreviewed"),
        _row("needs_review"),
        _row("needs_review", correspondent=None),
    ]

    summary = summarize_review_rows(rows)

    assert summary["total"] == 5
    assert summary["reviewed"] == 2
    assert summary["unreviewed"] == 1
    assert summary["needs_review"] == 2


def test_attention_counters_only_count_unreviewed_documents() -> None:
    rows = [
        # still to work through
        _row("unreviewed", correspondent=None, created="2026-09-20", added="2026-09-20T08:00:00"),
        _row("unreviewed", document_date="2026-09-01", added="2026-09-20T08:00:00"),
        # already handled / other state: not counted
        _row("reviewed", correspondent=None, created="2026-09-20", added="2026-09-20T08:00:00"),
        _row("needs_review", correspondent=None, created="2026-09-20", added="2026-09-20T08:00:00"),
    ]

    summary = summarize_review_rows(rows)

    assert summary["no_correspondent"] == 1
    assert summary["issue_date_is_import_date"] == 1


def test_unknown_status_counts_as_unreviewed_and_empty_is_zero() -> None:
    assert summarize_review_rows([])["total"] == 0
    summary = summarize_review_rows([{"id": 1}])
    assert summary["unreviewed"] == 1
