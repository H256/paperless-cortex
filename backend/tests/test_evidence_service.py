from __future__ import annotations

from app.services.evidence import resolve_evidence_matches


def test_resolve_evidence_uses_provided_bbox_when_valid():
    matches = resolve_evidence_matches(
        [{"doc_id": 1756, "page": 3, "snippet": "x", "bbox": [10, 20, 30, 40]}],
        max_pages=3,
    )
    assert len(matches) == 1
    assert matches[0]["status"] == "ok"
    assert matches[0]["bbox"] == [10.0, 20.0, 30.0, 40.0]


def test_resolve_evidence_returns_no_match_without_bbox():
    matches = resolve_evidence_matches(
        [{"doc_id": 1756, "page": 3, "snippet": "valid snippet", "bbox": None}],
        max_pages=3,
    )
    assert len(matches) == 1
    assert matches[0]["status"] == "no_match"
    assert matches[0]["bbox"] is None
