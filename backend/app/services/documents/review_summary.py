from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable


def _day_of(value: object) -> str:
    return value[:10] if isinstance(value, str) else ""


def issue_date_is_import_date(row: dict[str, object]) -> bool:
    """True when the issue date falls on the import day (Paperless fell back to "today")."""
    issue_day = _day_of(row.get("document_date")) or _day_of(row.get("created"))
    added_day = _day_of(row.get("added"))
    return bool(issue_day) and issue_day == added_day


def summarize_review_rows(rows: Iterable[dict[str, object]]) -> dict[str, int]:
    """Count review progress from list rows that carry a derived ``review_status``.

    ``no_correspondent`` and ``issue_date_is_import_date`` only count documents that
    are still *unreviewed*, because those are the ones left to work through.
    """
    summary = {
        "total": 0,
        "reviewed": 0,
        "unreviewed": 0,
        "needs_review": 0,
        "no_correspondent": 0,
        "issue_date_is_import_date": 0,
    }
    for row in rows:
        summary["total"] += 1
        status = row.get("review_status")
        if status == "reviewed":
            summary["reviewed"] += 1
            continue
        if status == "needs_review":
            summary["needs_review"] += 1
            continue
        summary["unreviewed"] += 1
        if row.get("correspondent") is None:
            summary["no_correspondent"] += 1
        if issue_date_is_import_date(row):
            summary["issue_date_is_import_date"] += 1
    return summary
