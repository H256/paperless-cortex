from __future__ import annotations

import json


def parse_string_list_json(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except Exception:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(value).strip() for value in parsed if str(value).strip()]


def normalize_string_list(values: list[str]) -> list[str]:
    cleaned = [str(value).strip() for value in values if str(value).strip()]
    return sorted(set(cleaned), key=str.lower)


def dumps_normalized_string_list(values: list[str]) -> str:
    return json.dumps(normalize_string_list(values), ensure_ascii=False)
