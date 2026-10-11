from __future__ import annotations

import datetime
from typing import Any

from app.services.ai.suggestion_warnings import compute_suggestion_warnings


def test_no_warnings_for_plausible_payload() -> None:
    ref = datetime.date(2026, 10, 11)
    payload: dict[str, Any] = {
        "date": "2026-01-15",
        "title": "Invoice from Acme",
        "correspondent": "Acme",
        "tags": ["invoice"],
    }
    assert compute_suggestion_warnings(payload, ["Acme", "Other"], ref) == []


def test_future_date_is_flagged() -> None:
    ref = datetime.date(2026, 10, 11)
    assert compute_suggestion_warnings({"date": "2026-12-31"}, [], ref) == [
        "Date 2026-12-31 is in the future"
    ]


def test_same_day_date_is_not_flagged() -> None:
    ref = datetime.date(2026, 10, 11)
    assert compute_suggestion_warnings({"date": "2026-10-11"}, [], ref) == []


def test_past_date_is_not_flagged() -> None:
    ref = datetime.date(2026, 10, 11)
    assert compute_suggestion_warnings({"date": "2026-01-15"}, [], ref) == []


def test_malformed_date_is_not_flagged() -> None:
    ref = datetime.date(2026, 10, 11)
    assert compute_suggestion_warnings({"date": "not-a-date"}, [], ref) == []


def test_filename_like_title_is_flagged() -> None:
    ref = datetime.date(2026, 10, 11)
    assert compute_suggestion_warnings({"title": "scan_2026-01-15.pdf"}, [], ref) == [
        "Title 'scan_2026-01-15.pdf' looks like a filename"
    ]


def test_path_like_title_is_flagged() -> None:
    ref = datetime.date(2026, 10, 11)
    assert compute_suggestion_warnings({"title": "docs/report.pdf"}, [], ref) == [
        "Title 'docs/report.pdf' looks like a filename"
    ]


def test_prose_title_with_period_is_not_flagged() -> None:
    ref = datetime.date(2026, 10, 11)
    assert compute_suggestion_warnings({"title": "Section 3.5 of the contract"}, [], ref) == []


def test_unknown_correspondent_is_flagged() -> None:
    ref = datetime.date(2026, 10, 11)
    assert compute_suggestion_warnings({"correspondent": "Unknown Co"}, ["Acme"], ref) == [
        "Correspondent 'Unknown Co' is not a known correspondent"
    ]


def test_known_correspondent_is_case_insensitive() -> None:
    ref = datetime.date(2026, 10, 11)
    assert compute_suggestion_warnings({"correspondent": "acme"}, ["Acme"], ref) == []


def test_empty_correspondent_is_not_flagged() -> None:
    ref = datetime.date(2026, 10, 11)
    assert compute_suggestion_warnings({"correspondent": ""}, [], ref) == []


def test_multiple_warnings_aggregate() -> None:
    ref = datetime.date(2026, 10, 11)
    payload: dict[str, Any] = {
        "date": "2027-01-01",
        "title": "scan.pdf",
        "correspondent": "Nobody",
    }
    warnings = compute_suggestion_warnings(payload, ["Acme"], ref)
    assert warnings == [
        "Date 2027-01-01 is in the future",
        "Title 'scan.pdf' looks like a filename",
        "Correspondent 'Nobody' is not a known correspondent",
    ]


def test_none_payload_returns_empty() -> None:
    ref = datetime.date(2026, 10, 11)
    assert compute_suggestion_warnings(None, [], ref) == []


def test_empty_known_correspondents_flags_any_nonempty() -> None:
    ref = datetime.date(2026, 10, 11)
    assert compute_suggestion_warnings({"correspondent": "X"}, [], ref) == [
        "Correspondent 'X' is not a known correspondent"
    ]


def test_similar_docs_metadata_shape_does_not_false_positive() -> None:
    # similar_docs metadata has no `date` key and a single-string correspondent;
    # a plausible-looking metadata dict must not raise warnings.
    ref = datetime.date(2026, 10, 11)
    metadata: dict[str, Any] = {
        "tags": ["invoice"],
        "correspondent": "Acme",
        "documentType": None,
        "language": None,
    }
    assert compute_suggestion_warnings(metadata, ["Acme"], ref) == []
