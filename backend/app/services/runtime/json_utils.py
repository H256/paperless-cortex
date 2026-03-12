from __future__ import annotations

import json
from typing import Any


def parse_json_object(raw: str | None) -> dict[str, Any]:
    """Safely parse a JSON string into a dictionary.

    Returns an empty dict if parsing fails or result is not a dict.

    Args:
        raw: JSON string to parse, or None

    Returns:
        Parsed dictionary, or empty dict on error

    Example:
        >>> parse_json_object('{"key": "value"}')
        {'key': 'value'}
        >>> parse_json_object(None)
        {}
        >>> parse_json_object('invalid json')
        {}
    """
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def parse_json_list(raw: str | None) -> list[Any]:
    """Safely parse a JSON string into a list.

    Returns an empty list if parsing fails or result is not a list.

    Args:
        raw: JSON string to parse, or None

    Returns:
        Parsed list, or empty list on error

    Example:
        >>> parse_json_list('[1, 2, 3]')
        [1, 2, 3]
        >>> parse_json_list(None)
        []
    """
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return payload if isinstance(payload, list) else []
