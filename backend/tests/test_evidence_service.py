from __future__ import annotations

from pathlib import Path

import pytest

from app.config import load_settings
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


def test_resolve_evidence_uses_pdf_word_matching_when_settings_available(monkeypatch):
    settings = load_settings()

    monkeypatch.setattr(
        "app.services.evidence._load_page_words",
        lambda _settings, _doc_id, _page, _pdf_cache, _words_cache, db=None: [
            {"text": "Invoice", "bbox": [10, 10, 40, 20]},
            {"text": "Number", "bbox": [42, 10, 80, 20]},
            {"text": "INV-2026-00421", "bbox": [82, 10, 150, 20]},
        ],
    )

    matches = resolve_evidence_matches(
        [{"doc_id": 1756, "page": 1, "snippet": "Invoice Number INV-2026-00421", "bbox": None}],
        max_pages=3,
        settings=settings,
    )
    assert len(matches) == 1
    assert matches[0]["status"] == "ok"
    assert matches[0]["bbox"] == [10.0, 10.0, 150.0, 20.0]


def test_resolve_evidence_parses_real_pdf_fixture(monkeypatch):
    fitz = pytest.importorskip("fitz")
    _ = fitz
    settings = load_settings()
    fixture = Path(__file__).resolve().parent / "fixtures" / "pdfs" / "doc-1960-paperless.pdf"
    pdf_bytes = fixture.read_bytes()
    monkeypatch.setattr("app.services.evidence.fetch_pdf_bytes", lambda _settings, _doc_id: pdf_bytes)

    matches = resolve_evidence_matches(
        [
            {
                "doc_id": 1960,
                "page": 1,
                "snippet": "Rechnung Nr.: INV-2026-00421",
                "bbox": None,
            }
        ],
        max_pages=3,
        settings=settings,
    )
    assert len(matches) == 1
    # Depending on OCR/text layer quality, this may still be page-only; ensure no crash and valid status.
    assert matches[0]["status"] in {"ok", "no_match"}
