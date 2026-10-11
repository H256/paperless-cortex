from __future__ import annotations

import json
from typing import Any

_JSON_DECODER = json.JSONDecoder()


def _strip_trailing_commas(s: str) -> str:
    """Remove trailing commas before ``}``/``]`` that sit outside string literals.

    Unlike a blanket ``str.replace(",}", "}")`` this never touches the
    substring inside a string value, so content such as ``"foo,} bar"`` is
    preserved while a genuinely dangling ``[1, 2,]`` is still closed cleanly.
    """
    out: list[str] = []
    in_string = False
    escape = False
    for ch in s:
        if escape:
            out.append(ch)
            escape = False
            continue
        if ch == "\\":
            out.append(ch)
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            out.append(ch)
            continue
        if in_string:
            out.append(ch)
            continue
        if ch in "}]":
            while out and out[-1] in ", ":
                out.pop()
        out.append(ch)
    return "".join(out)


def repair_truncated_json_object(raw: str) -> dict[str, Any] | None:
    candidate = str(raw or "").strip()
    if not candidate or not candidate.startswith("{"):
        return None
    try:
        parsed = json.loads(candidate)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
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
    repaired = _strip_trailing_commas(repaired)
    try:
        parsed = json.loads(repaired)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    # The original was truncated (we had to close strings/braces), so flag the
    # recovered object as partial so callers can surface it rather than treat it
    # as a complete suggestion.
    parsed["truncated"] = True
    return parsed


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
        except (json.JSONDecodeError, ValueError):
            pass
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(raw[start : end + 1])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            # A "}" inside a string value (or other malformation) makes the
            # rfind slice invalid; fall through to the truncation repair.
            pass
    if start != -1:
        repaired = repair_truncated_json_object(raw[start:])
        if repaired is not None:
            return repaired
    raise ValueError("No JSON object found in response")
