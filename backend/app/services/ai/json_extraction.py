from __future__ import annotations

import json

from typing import Any


_JSON_DECODER = json.JSONDecoder()


def repair_truncated_json_object(raw: str) -> dict[str, Any] | None:
    candidate = str(raw or "").strip()
    if not candidate or not candidate.startswith("{"):
        return None
    try:
        parsed = json.loads(candidate)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        pass

    in_string = False
    escape = False
    brace_depth = 0
    for ch in candidate:
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            brace_depth += 1
        elif ch == "}":
            brace_depth = max(0, brace_depth - 1)

    repaired = candidate
    if in_string:
        repaired += '"'
    if brace_depth > 0:
        repaired += "}" * brace_depth
    repaired = repaired.replace(",}", "}").replace(",]", "]")
    try:
        parsed = json.loads(repaired)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def extract_json_object(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = raw.removeprefix("```json").removeprefix("```").strip()
        if raw.endswith("```"):
            raw = raw[:-3].strip()
    if raw.startswith("{") and raw.endswith("}"):
        return json.loads(raw)
    start = raw.find("{")
    if start != -1:
        try:
            parsed, _end = _JSON_DECODER.raw_decode(raw[start:])
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(raw[start : end + 1])
    if start != -1:
        repaired = repair_truncated_json_object(raw[start:])
        if repaired is not None:
            return repaired
    raise ValueError("No JSON object found in response")
