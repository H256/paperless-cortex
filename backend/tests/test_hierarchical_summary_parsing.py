from __future__ import annotations

from app.services.hierarchical_summary import (
    _coerce_page_notes_payload,
    _extract_json_dict,
    _parse_page_notes_text,
)


def test_extract_json_dict_accepts_code_fence():
    raw = """```json
{"page":1,"facts":["alpha"],"entities":[],"references":[],"key_numbers":[],"uncertainties":[]}
```"""
    parsed = _extract_json_dict(raw)
    assert parsed["page"] == 1
    assert parsed["facts"] == ["alpha"]


def test_coerce_page_notes_payload_normalizes_and_sets_page():
    parsed = {
        "page": "999",
        "facts": [" A ", 123, "", None],
        "entities": "invalid",
        "references": ["R1"],
        "key_numbers": [42],
        "uncertainties": [],
    }
    payload = _coerce_page_notes_payload(7, parsed)
    assert payload["page"] == 7
    assert payload["facts"] == ["A", "123", "None"]
    assert payload["entities"] == []
    assert payload["references"] == ["R1"]
    assert payload["key_numbers"] == ["42"]


def test_coerce_page_notes_payload_adds_fallback_excerpt_when_empty():
    payload = _coerce_page_notes_payload(
        3,
        {"facts": [], "entities": [], "references": [], "key_numbers": [], "uncertainties": []},
        raw_fallback="Some model prose without JSON structure.",
    )
    assert payload["page"] == 3
    assert any("fallback_raw_excerpt:" in item for item in payload["uncertainties"])


def test_parse_page_notes_text_from_markdown_sections():
    raw = """
Facts:
- Steuerrelevanter Gewinn: 8284,92 EUR
- Zeitraum: 2021
Entities:
- Binance
References:
- Anlage SO
Key numbers:
- 8284,92 EUR
- 600,00 EUR
Uncertainties:
- OCR bei Zeile 3 unsicher
"""
    payload = _parse_page_notes_text(2, raw)
    assert payload["page"] == 2
    assert "Steuerrelevanter Gewinn: 8284,92 EUR" in payload["facts"]
    assert payload["entities"] == ["Binance"]
    assert payload["references"] == ["Anlage SO"]
    assert "8284,92 EUR" in payload["key_numbers"]


def test_parse_page_notes_text_fallbacks_without_headings():
    raw = "Veräußerungsgewinn 8284,92 EUR\nFreigrenze 600,00 EUR\n"
    payload = _parse_page_notes_text(5, raw)
    assert payload["page"] == 5
    assert payload["facts"]
    assert payload["key_numbers"]
