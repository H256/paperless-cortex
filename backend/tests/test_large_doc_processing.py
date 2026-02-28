from __future__ import annotations

from app.services.ai.hierarchical_summary import group_notes_into_sections
from app.services.text_cleaning import clean_ocr_text, estimate_tokens


def test_clean_ocr_text_dehyphenates_and_joins_lines():
    raw = "Rech-\nnung\nPage 12\nBetrag: 10,00 EUR"
    cleaned = clean_ocr_text(raw)
    assert "Rechnung" in cleaned
    assert "Page 12" not in cleaned
    assert "Betrag: 10,00 EUR" in cleaned


def test_group_notes_into_sections_respects_token_budget():
    notes = [
        (1, {"facts": ["A" * 1200]}),
        (2, {"facts": ["B" * 1200]}),
        (3, {"facts": ["C" * 1200]}),
    ]
    sections = group_notes_into_sections(
        notes,
        max_pages=10,
        max_input_tokens=700,
    )
    assert len(sections) >= 2
    assert sections[0][0].startswith("1-")


def test_estimate_tokens_non_empty():
    assert estimate_tokens("abcde" * 10) > 0


def test_clean_ocr_text_strips_html_and_flattens_table():
    raw = "<table><tr><td>Datum</td><td>2024-01-01</td></tr><tr><td>Betrag</td><td>19,99 EUR</td></tr></table>"
    cleaned = clean_ocr_text(raw)
    assert "<table>" not in cleaned
    assert "Datum | 2024-01-01" in cleaned
    assert "Betrag | 19,99 EUR" in cleaned
