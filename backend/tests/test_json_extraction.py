from __future__ import annotations

from app.services.ai.json_extraction import (
    extract_json_object,
    repair_truncated_json_object,
)


def test_repair_preserves_comma_brace_inside_string_value() -> None:
    # AUDIT AI-009: the old blanket str.replace(",}", "}") corrupted any
    # ",}" that appeared inside a string value. A truncated object whose
    # string value contains ",}" must keep the substring intact.
    result = repair_truncated_json_object('{"summary": "text,} more')
    assert result is not None
    assert result["summary"] == "text,} more"


def test_repair_flags_truncated_payload() -> None:
    # A truncated object (had to close a string/brace) must be flagged so the
    # UI/writeback can surface it as partial rather than treat it as complete.
    result = repair_truncated_json_object('{"summary": "partial text')
    assert result is not None
    assert result["truncated"] is True


def test_repair_strips_trailing_comma_before_brace() -> None:
    # A dangling trailing comma before the implicit closing brace is removed
    # cleanly without corrupting other content.
    result = repair_truncated_json_object('{"a": 1, "b": 2,')
    assert result is not None
    assert result["a"] == 1
    assert result["b"] == 2
    assert result["truncated"] is True


def test_repair_preserves_comma_bracket_inside_string_value() -> None:
    # Symmetric guard for the ",]" substring inside a string value.
    result = repair_truncated_json_object('{"note": "a,] b')
    assert result is not None
    assert result["note"] == "a,] b"


def test_complete_object_is_not_flagged_truncated() -> None:
    # A well-formed object parses on the fast path and must NOT be flagged.
    result = repair_truncated_json_object('{"a": 1}')
    assert result is not None
    assert "truncated" not in result


def test_extract_json_object_propagates_truncation_flag() -> None:
    # The truncation marker must survive the extract_json_object wrapper so the
    # suggestion payload carries it end-to-end.
    result = extract_json_object('{"summary": "text,} more')
    assert result["summary"] == "text,} more"
    assert result["truncated"] is True


def test_extract_json_object_complete_not_flagged() -> None:
    result = extract_json_object('{"a": 1}')
    assert "truncated" not in result
