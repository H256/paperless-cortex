from __future__ import annotations

from app.services.hierarchical_summary import (
    _coerce_page_notes_payload,
    _extract_json_dict,
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
