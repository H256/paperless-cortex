from __future__ import annotations

from app.services.writeback.writeback_plan import (
    canonical_ai_summary,
    compare_document_fields,
    extract_ai_summary_note,
)


def test_extract_ai_summary_note_detects_marker():
    note_id, note_text = extract_ai_summary_note(
        [
            {"id": 1, "note": "foo"},
            {"id": 2, "note": "Kurztext\n\nModel:x\nKI-Zusammenfassung"},
        ]
    )
    assert note_id == 2
    assert note_text and note_text.endswith("KI-Zusammenfassung")


def test_canonical_ai_summary_ignores_marker_meta_line():
    text = "Zusammenfassung Inhalt\n\nModel:gpt\nKI-Zusammenfassung"
    assert canonical_ai_summary(text) == "Zusammenfassung Inhalt"


def test_compare_document_fields_detects_note_change_only():
    changed, payload = compare_document_fields(
        local_title="A",
        remote_title="A",
        local_date="2024-01-01",
        remote_date="2024-01-01",
        local_correspondent_id=10,
        remote_correspondent_id=10,
        local_tags=[1, 2],
        remote_tags=[2, 1],
        local_ai_note="Neu\n\nModel:x\nKI-Zusammenfassung",
        remote_ai_note="Alt\n\nModel:y\nKI-Zusammenfassung",
    )
    assert changed == ["note"]
    assert payload.get("note_action") == "replace"
