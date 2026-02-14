from __future__ import annotations

from app.services.json_utils import parse_json_object


def test_parse_json_object_returns_empty_for_invalid_inputs() -> None:
    assert parse_json_object(None) == {}
    assert parse_json_object("") == {}
    assert parse_json_object("{") == {}
    assert parse_json_object("[]") == {}
    assert parse_json_object('"text"') == {}


def test_parse_json_object_returns_dict_for_object_payload() -> None:
    parsed = parse_json_object('{"a":1,"b":"x"}')
    assert parsed == {"a": 1, "b": "x"}
