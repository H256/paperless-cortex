from __future__ import annotations

from app.services.string_list_json import (
    dumps_normalized_string_list,
    normalize_string_list,
    parse_string_list_json,
)


def test_parse_string_list_json_handles_invalid_payloads() -> None:
    assert parse_string_list_json(None) == []
    assert parse_string_list_json("") == []
    assert parse_string_list_json("{") == []
    assert parse_string_list_json('{"a":1}') == []


def test_parse_string_list_json_trims_and_filters() -> None:
    parsed = parse_string_list_json('["  Alpha  ", "", " Beta ", 3, null]')
    assert parsed == ["Alpha", "Beta", "3"]


def test_normalize_and_dump_string_list() -> None:
    normalized = normalize_string_list([" beta ", "Alpha", "alpha", "", "Beta"])
    assert normalized == ["Alpha", "alpha", "Beta", "beta"]
    dumped = dumps_normalized_string_list([" z ", "A", "a", ""])
    assert dumped == '["A", "a", "z"]'
