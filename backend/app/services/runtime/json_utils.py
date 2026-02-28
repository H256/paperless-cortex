from __future__ import annotations

import json
from typing import Any


def parse_json_object(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def parse_json_list(raw: str | None) -> list[Any]:
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except Exception:
        return []
    return payload if isinstance(payload, list) else []
