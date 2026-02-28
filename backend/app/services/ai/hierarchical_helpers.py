from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.services.ai.json_extraction import extract_json_object
from app.services.ai.text_budget import truncate_for_tokens

logger = logging.getLogger(__name__)

_PAGE_NOTES_CONTENT_KEYS = ("facts", "entities", "references", "key_numbers")
_PAGE_NOTES_ALL_KEYS = (*_PAGE_NOTES_CONTENT_KEYS, "uncertainties")
_PAGE_NOTES_SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "facts": ("facts", "fakten"),
    "entities": ("entities", "entitaeten"),
    "references": ("references", "referenzen", "belege"),
    "key_numbers": ("key numbers", "key_numbers", "zahlen", "kennzahlen"),
    "uncertainties": ("uncertainties", "unsicherheiten"),
}
_PAGE_NOTES_HEADING_TO_KEY: dict[str, str] = {
    re.sub(r"[^a-z0-9]+", " ", alias.lower()).strip(): key
    for key, aliases in _PAGE_NOTES_SECTION_ALIASES.items()
    for alias in aliases
}
_BULLET_PREFIX_RE = re.compile(r"^(?:[-*]|\u2022|\d+[.)])\s*")
_NUMBER_TOKEN_RE = re.compile(
    r"\b(?:\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?(?:\s?(?:EUR|USD|CHF|%))?|\d{4}-\d{2}-\d{2})\b"
)
_DATE_TOKEN_RE = re.compile(r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}[./-]\d{1,2}[./-]\d{2,4})\b")
_CONTROL_TOKEN_RE = re.compile(r"<\|[^>]+\|>")
_PROMPT_ECHO_MARKERS = (
    "extract structured page notes from ocr text",
    "return plain text with exactly these headings",
    "facts:",
    "entities:",
    "references:",
    "key numbers:",
    "uncertainties:",
    "do not invent information",
)
_SUMMARY_META_MARKERS = (
    "we need to extract structured page notes",
    "given ocr text",
    "interpretation:",
    "return plain text with exactly these headings",
    "facts:",
    "entities:",
    "references:",
    "key numbers:",
    "uncertainties:",
)
_SUMMARY_META_STRONG_MARKERS = (
    "we need to extract structured page notes",
    "return plain text with exactly these headings",
    "extract structured page notes from ocr text",
    "given ocr text",
)


def _extract_json_dict(text: str) -> dict[str, Any]:
    return extract_json_object(text)


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _normalize_heading(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def _normalize_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    cleaned: list[str] = []
    for item in values:
        text = str(item).strip()
        if text:
            cleaned.append(text)
    return cleaned


def _coerce_page_notes_payload(
    page: int,
    payload: dict[str, Any],
    raw_fallback: str | None = None,
) -> dict[str, Any]:
    result = {"page": int(page)}
    for key in _PAGE_NOTES_ALL_KEYS:
        result[key] = _normalize_list(payload.get(key))
    if raw_fallback and not any(result[key] for key in _PAGE_NOTES_CONTENT_KEYS):
        compact = " ".join((raw_fallback or "").split())
        if compact:
            result["uncertainties"].append(f"fallback_raw_excerpt:{compact[:240]}")
    return result


def _best_effort_page_notes_from_text(page: int, raw_text: str) -> dict[str, Any]:
    lines = [line.strip(" -*\t") for line in (raw_text or "").splitlines()]
    lines = [line for line in lines if line]
    facts = [line for line in lines[:8] if len(line) > 3]
    number_matches = _NUMBER_TOKEN_RE.findall(raw_text or "")
    return {
        "page": int(page),
        "facts": facts[:8],
        "entities": [],
        "references": [],
        "key_numbers": [str(v) for v in number_matches[:12]],
        "uncertainties": ["model_returned_non_json"],
    }


def _parse_page_notes_text(page: int, text: str) -> dict[str, Any]:
    values: dict[str, list[str]] = {key: [] for key in _PAGE_NOTES_ALL_KEYS}
    current_key: str | None = None
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        heading = _normalize_heading(line.rstrip(":").strip())
        resolved = _PAGE_NOTES_HEADING_TO_KEY.get(heading)
        if resolved:
            current_key = resolved
            continue
        bullet = _BULLET_PREFIX_RE.sub("", line).strip()
        if not bullet:
            continue
        if current_key:
            values[current_key].append(bullet)

    payload = _coerce_page_notes_payload(page, values, raw_fallback=text)
    if any(payload[key] for key in _PAGE_NOTES_CONTENT_KEYS):
        return payload
    return _best_effort_page_notes_from_text(page, text)


def _truncate_for_tokens(text: str, max_input_tokens: int) -> str:
    return truncate_for_tokens(text, max_input_tokens)


def _raw_preview(raw: str | None, max_chars: int = 500) -> str:
    preview = str(raw or "").replace("\n", "\\n")
    if len(preview) > max_chars:
        return preview[:max_chars] + "...<truncated>"
    return preview


def _sanitize_model_output_text(text: str) -> str:
    raw = str(text or "")
    if not raw:
        return ""
    cleaned = _CONTROL_TOKEN_RE.sub("", raw)
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _looks_like_prompt_echo_or_meta(text: str) -> bool:
    normalized = " ".join((text or "").lower().split())
    if not normalized:
        return False
    if "<|channel|>" in normalized or "<|message|>" in normalized:
        return True
    marker_hits = sum(1 for marker in _PROMPT_ECHO_MARKERS if marker in normalized)
    return marker_hits >= 3


def _is_summary_meta_text(text: str) -> bool:
    normalized = " ".join((text or "").lower().split())
    if not normalized:
        return True
    if "<|channel|>" in normalized or "<|message|>" in normalized:
        return True
    if any(marker in normalized for marker in _SUMMARY_META_STRONG_MARKERS):
        return True
    if _looks_like_prompt_echo_or_meta(normalized):
        return True
    hits = sum(1 for marker in _SUMMARY_META_MARKERS if marker in normalized)
    return hits >= 2


def _sanitize_summary_value(value: Any, *, max_chars: int = 360) -> str:
    text = _sanitize_model_output_text(str(value or ""))
    text = " ".join(text.split()).strip()
    if not text:
        return ""
    if _is_summary_meta_text(text):
        return ""
    if len(text) > max_chars:
        text = text[: max_chars - 3].rstrip() + "..."
    return text


def _sanitize_summary_list(values: Any, *, max_items: int, max_chars: int) -> list[str]:
    if not isinstance(values, list):
        return []
    cleaned: list[str] = []
    for value in values:
        text = _sanitize_summary_value(value, max_chars=max_chars)
        if not text:
            continue
        cleaned.append(text)
        if len(cleaned) >= max_items:
            break
    return list(dict.fromkeys(cleaned))


def _normalize_section_summary_payload(section_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    summary = _sanitize_summary_value(payload.get("summary"), max_chars=700)
    key_facts = _sanitize_summary_list(payload.get("key_facts"), max_items=10, max_chars=320)
    key_dates = _sanitize_summary_list(payload.get("key_dates"), max_items=10, max_chars=120)
    key_entities = _sanitize_summary_list(payload.get("key_entities"), max_items=10, max_chars=180)
    key_numbers = _sanitize_summary_list(payload.get("key_numbers"), max_items=16, max_chars=120)
    open_questions = _sanitize_summary_list(payload.get("open_questions"), max_items=10, max_chars=220)
    confidence_notes = _sanitize_summary_list(payload.get("confidence_notes"), max_items=8, max_chars=240)
    if not summary:
        summary = " ".join(key_facts[:3]).strip()
    if not summary:
        summary = f"Section {section_key} summary generated with sanitization fallback."
    return {
        "section": section_key,
        "text": summary,
        "summary": summary,
        "key_facts": key_facts,
        "key_dates": key_dates,
        "key_entities": key_entities,
        "key_numbers": key_numbers,
        "open_questions": open_questions,
        "confidence_notes": confidence_notes,
    }


def _page_note_payload_to_text(payload: dict[str, Any]) -> str:
    direct_text = _sanitize_summary_value(payload.get("text"), max_chars=2000)
    if direct_text:
        return direct_text
    lines: list[str] = []
    for key, label in (
        ("facts", "Facts"),
        ("entities", "Entities"),
        ("references", "References"),
        ("key_numbers", "Key numbers"),
        ("uncertainties", "Uncertainties"),
    ):
        values = _sanitize_summary_list(payload.get(key), max_items=16, max_chars=240)
        if not values:
            continue
        lines.append(f"{label}:")
        lines.extend(f"- {value}" for value in values)
    return "\n".join(lines).strip()


def _section_notes_to_text(page_notes: list[dict[str, Any]], *, max_input_tokens: int) -> str:
    from app.services.documents.text_cleaning import estimate_tokens

    budget = max(1000, int(max_input_tokens))
    blocks: list[str] = []
    used = 0
    for note in page_notes:
        if not isinstance(note, dict):
            continue
        page_no = int(note.get("page") or 0)
        text = _page_note_payload_to_text(note)
        if not text:
            continue
        block = f"Page {page_no}:\n{text}" if page_no > 0 else text
        block_tokens = estimate_tokens(block)
        if blocks and used + block_tokens > budget:
            break
        blocks.append(block)
        used += block_tokens
    if not blocks:
        return ""
    return _truncate_for_tokens("\n\n".join(blocks), max_input_tokens=budget)


def _compact_text_items(values: Any, *, max_items: int, max_chars: int) -> list[str]:
    if not isinstance(values, list):
        return []
    items: list[str] = []
    for value in values:
        text = _sanitize_model_output_text(str(value or ""))
        text = " ".join(text.split()).strip()
        if not text:
            continue
        if _is_summary_meta_text(text):
            continue
        if len(text) > max_chars:
            text = text[: max_chars - 3].rstrip() + "..."
        items.append(text)
        if len(items) >= max_items:
            break
    return items


def _compact_page_note_for_section(note: dict[str, Any]) -> dict[str, Any]:
    page = int(note.get("page") or 0)
    return {
        "page": page,
        "facts": _compact_text_items(note.get("facts"), max_items=4, max_chars=180),
        "entities": _compact_text_items(note.get("entities"), max_items=4, max_chars=80),
        "references": _compact_text_items(note.get("references"), max_items=3, max_chars=120),
        "key_numbers": _compact_text_items(note.get("key_numbers"), max_items=6, max_chars=60),
        "uncertainties": _compact_text_items(note.get("uncertainties"), max_items=2, max_chars=120),
    }


def _compact_page_notes_for_section(
    page_notes: list[dict[str, Any]],
    *,
    max_input_tokens: int,
) -> str:
    from app.services.documents.text_cleaning import estimate_tokens

    budget = max(1000, int(max_input_tokens))
    compact_notes: list[dict[str, Any]] = []
    current_tokens = 0
    for note in page_notes:
        if not isinstance(note, dict):
            continue
        compact = _compact_page_note_for_section(note)
        compact_json = _json_dumps(compact)
        note_tokens = estimate_tokens(compact_json)
        if compact_notes and current_tokens + note_tokens > budget:
            break
        compact_notes.append(compact)
        current_tokens += note_tokens
    if not compact_notes and page_notes:
        first = page_notes[0] if isinstance(page_notes[0], dict) else {}
        compact_notes.append(_compact_page_note_for_section(first))
    return _truncate_for_tokens(_json_dumps(compact_notes), max_input_tokens=budget)


def _best_effort_section_summary(
    *,
    section_key: str,
    page_notes: list[dict[str, Any]],
    reason: str,
) -> dict[str, Any]:
    facts: list[str] = []
    entities: list[str] = []
    numbers: list[str] = []
    dates: list[str] = []
    for note in page_notes:
        note_facts = note.get("facts") if isinstance(note, dict) else []
        if isinstance(note_facts, list):
            for item in note_facts:
                text = _sanitize_summary_value(item, max_chars=320)
                if text:
                    facts.append(text)
                    dates.extend(_DATE_TOKEN_RE.findall(text))
                    numbers.extend(_NUMBER_TOKEN_RE.findall(text))
        note_entities = note.get("entities") if isinstance(note, dict) else []
        if isinstance(note_entities, list):
            for item in note_entities:
                text = _sanitize_summary_value(item, max_chars=180)
                if text:
                    entities.append(text)
        note_numbers = note.get("key_numbers") if isinstance(note, dict) else []
        if isinstance(note_numbers, list):
            for item in note_numbers:
                text = _sanitize_summary_value(item, max_chars=120)
                if text:
                    numbers.append(text)

    def uniq(values: list[str]) -> list[str]:
        return list(dict.fromkeys(v for v in values if v))

    facts_u = uniq(facts)[:8]
    entities_u = uniq(entities)[:8]
    numbers_u = uniq(numbers)[:10]
    dates_u = uniq(dates)[:8]
    summary = " ".join(facts_u[:4]).strip()
    if not summary:
        summary = f"Section {section_key} was summarized using deterministic fallback due to malformed model JSON."
    payload = {
        "section": section_key,
        "summary": summary,
        "key_facts": facts_u,
        "key_dates": dates_u,
        "key_entities": entities_u,
        "key_numbers": numbers_u,
        "open_questions": [],
        "confidence_notes": [reason],
    }
    return _normalize_section_summary_payload(section_key, payload)


def _best_effort_global_summary(
    *,
    section_summaries: list[dict[str, Any]],
    reason: str,
) -> dict[str, Any]:
    summaries: list[str] = []
    facts: list[str] = []
    entities: list[str] = []
    numbers: list[str] = []
    dates: list[str] = []
    open_questions: list[str] = []
    confidence_notes: list[str] = []

    for section in section_summaries:
        if not isinstance(section, dict):
            continue
        summary = str(section.get("summary") or "").strip()
        if summary:
            summaries.append(summary)
            dates.extend(_DATE_TOKEN_RE.findall(summary))
            numbers.extend(_NUMBER_TOKEN_RE.findall(summary))
        for key, target in (
            ("key_facts", facts),
            ("key_entities", entities),
            ("key_numbers", numbers),
            ("key_dates", dates),
            ("open_questions", open_questions),
            ("confidence_notes", confidence_notes),
        ):
            values = section.get(key)
            if not isinstance(values, list):
                continue
            for value in values:
                text = str(value).strip()
                if text:
                    target.append(text)

    def uniq(values: list[str]) -> list[str]:
        return list(dict.fromkeys(v for v in values if v))

    facts_u = uniq(facts)[:20]
    entities_u = uniq(entities)[:20]
    numbers_u = uniq(numbers)[:24]
    dates_u = uniq(dates)[:20]
    open_q_u = uniq(open_questions)[:12]
    confidence_u = uniq(confidence_notes)[:8]

    summary_text = " ".join(summaries[:3]).strip()
    if not summary_text:
        summary_text = "Document summary synthesized from section summaries using deterministic fallback."
    executive = summaries[0].strip() if summaries else summary_text
    if len(executive) > 320:
        executive = executive[:317].rstrip() + "..."

    notes = [reason]
    notes.extend(confidence_u[:3])
    return {
        "summary": summary_text,
        "executive_summary": executive,
        "key_facts": facts_u,
        "key_dates": dates_u,
        "key_entities": entities_u,
        "key_numbers": numbers_u,
        "open_questions": open_q_u,
        "confidence_notes": uniq(notes),
    }
