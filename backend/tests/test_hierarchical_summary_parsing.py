from __future__ import annotations

from app.services.hierarchical_summary import (
    _best_effort_section_summary,
    _compact_page_notes_for_section,
    _coerce_page_notes_payload,
    _extract_json_dict,
    _parse_page_notes_text,
    generate_section_summary,
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


def test_extract_json_dict_repairs_truncated_object():
    raw = '{"section":"16-20","summary":"short","key_facts":["a","b"]'
    parsed = _extract_json_dict(raw)
    assert parsed["section"] == "16-20"
    assert parsed["key_facts"] == ["a", "b"]


def test_extract_json_dict_ignores_trailing_non_json_text():
    raw = '{"section":"16-20","summary":"ok","key_facts":[]}\nNOT JSON'
    parsed = _extract_json_dict(raw)
    assert parsed["section"] == "16-20"


def test_compact_page_notes_for_section_limits_payload_size():
    notes = [
        {
            "page": i,
            "facts": [f"Fact {i} " + ("x" * 400) for _ in range(10)],
            "entities": [f"Entity {j}" for j in range(10)],
            "references": [f"Reference {j}" for j in range(10)],
            "key_numbers": [str(1000 + j) for j in range(10)],
            "uncertainties": [f"Uncertainty {j}" for j in range(10)],
        }
        for i in range(1, 20)
    ]
    payload = _compact_page_notes_for_section(notes, max_input_tokens=1200)
    # Should keep payload significantly smaller than raw all-pages notes.
    assert len(payload) < 9000
    assert '"page": 1' in payload


def test_best_effort_section_summary_collects_core_fields():
    payload = _best_effort_section_summary(
        section_key="1-3",
        page_notes=[
            {
                "facts": ["Invoice dated 2026-02-10 amount 49,00 EUR", "Customer accepted terms."],
                "entities": ["PSD Bank"],
                "key_numbers": ["49,00 EUR"],
            }
        ],
        reason="fallback_due_to_json_parse_error:test",
    )
    assert payload["section"] == "1-3"
    assert payload["summary"]
    assert "49,00 EUR" in payload["key_numbers"]
    assert "2026-02-10" in payload["key_dates"]
    assert payload["confidence_notes"]


def test_generate_section_summary_falls_back_when_json_never_parses(monkeypatch):
    class StubSettings:
        text_model = "stub"
        section_summary_max_input_tokens = 6000
        section_summary_timeout_seconds = 30
        summary_max_output_tokens = 700

    monkeypatch.setattr(
        "app.services.hierarchical_summary.ensure_text_llm_ready",
        lambda _settings: None,
    )

    calls = {"count": 0}

    def _fake_chat(*_args, **_kwargs):
        calls["count"] += 1
        # No JSON object on both primary + compact retry.
        return "Summary text only without braces"

    monkeypatch.setattr("app.services.hierarchical_summary._chat_response", _fake_chat)
    payload = generate_section_summary(
        StubSettings(),
        section_key="10-12",
        page_notes=[{"facts": ["Fact A"], "entities": ["Entity B"], "key_numbers": ["12"]}],
    )
    assert payload["section"] == "10-12"
    assert payload["summary"]
    assert payload["confidence_notes"]
    assert calls["count"] >= 2
