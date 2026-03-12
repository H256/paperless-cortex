from __future__ import annotations

import json


def parse_string_list_json(raw: str | None) -> list[str]:
    """Parse a JSON array into a list of non-empty strings.

    Filters out None values and empty strings after trimming.

    Args:
        raw: JSON string containing an array, or None

    Returns:
        List of non-empty strings, or empty list on error

    Example:
        >>> parse_string_list_json('["tag1", "tag2", ""]')
        ['tag1', 'tag2']
        >>> parse_string_list_json(None)
        []
    """
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    values: list[str] = []
    for value in parsed:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            values.append(text)
    return values


def normalize_string_list(values: list[str]) -> list[str]:
    """Normalize a list of strings by removing duplicates and sorting.

    Deduplication is case-insensitive, but original casing is preserved.
    Sorting is case-insensitive (lowercase first, then original).

    Args:
        values: List of strings to normalize

    Returns:
        Deduplicated and sorted list of strings

    Example:
        >>> normalize_string_list(["apple", "Apple", "banana"])
        ['apple', 'banana']
    """
    cleaned = [str(value).strip() for value in values if str(value).strip()]
    return sorted(set(cleaned), key=lambda value: (value.lower(), value))


def dumps_normalized_string_list(values: list[str]) -> str:
    """Serialize a string list to JSON after normalization.

    Args:
        values: List of strings to normalize and serialize

    Returns:
        JSON array string with normalized values

    Example:
        >>> dumps_normalized_string_list(["tag2", "tag1", "tag1"])
        '["tag1", "tag2"]'
    """
    return json.dumps(normalize_string_list(values), ensure_ascii=False)
