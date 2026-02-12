from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import DocumentPageNote, DocumentSectionSummary
from app.services import llm_client
from app.services.guard import ensure_text_llm_ready
from app.services.text_cleaning import estimate_tokens

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
_JSON_DECODER = json.JSONDecoder()
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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_json_dict(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw)
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
        repaired = _repair_truncated_json_object(raw[start:])
        if repaired is not None:
            return repaired
    raise ValueError("No JSON object found in response")


def _repair_truncated_json_object(raw: str) -> dict[str, Any] | None:
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
    repaired = re.sub(r",(\s*[}\]])", r"\1", repaired)
    try:
        parsed = json.loads(repaired)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


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
    if max_input_tokens <= 0:
        return text
    max_chars = int(max_input_tokens * 3.5)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n[TRUNCATED]"


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


def _chat_json_response(
    settings: Settings,
    *,
    prompt: str,
    timeout: int,
    max_tokens: int,
) -> dict[str, Any]:
    raw = _chat_response(
        settings,
        prompt=prompt,
        timeout=timeout,
        max_tokens=max_tokens,
        json_mode=True,
    )
    return _extract_json_dict(raw)


def _chat_response(
    settings: Settings,
    *,
    prompt: str,
    timeout: int,
    max_tokens: int,
    json_mode: bool,
) -> str:
    return llm_client.chat_completion(
        settings,
        model=settings.text_model or "",
        messages=[{"role": "user", "content": prompt}],
        timeout=timeout,
        max_tokens=max_tokens,
        temperature=0.0,
        json_mode=json_mode,
    )


def _page_notes_prompt(page: int, text: str) -> str:
    return (
        "Extract structured page notes from OCR text.\n"
        "Return plain text with exactly these headings:\n"
        "Facts:\n"
        "Entities:\n"
        "References:\n"
        "Key numbers:\n"
        "Uncertainties:\n"
        "Use bullet points under each heading.\n"
        "Rules:\n"
        "- Keep facts concise and literal.\n"
        "- Include dates, amounts, ids in key_numbers if present.\n"
        "- Do not invent information.\n"
        f"Page: {page}\n"
        f"Text:\n{text}\n"
    )


def _page_notes_prompt_strict(page: int, text: str) -> str:
    return (
        "Extract structured page notes from OCR text.\n"
        "Output plain text only. No control tokens, no tags, no prose outside headings.\n"
        "Return exactly these headings in this order:\n"
        "Facts:\n"
        "Entities:\n"
        "References:\n"
        "Key numbers:\n"
        "Uncertainties:\n"
        "Use bullet points under each heading.\n"
        f"Page: {page}\n"
        f"Text:\n{text}\n"
    )


def _section_summary_prompt(section_key: str, page_notes_json: str) -> str:
    return (
        "Aggregate page notes into a concise section summary.\n"
        "Return plain text only.\n"
        "No JSON, no markdown, no XML/control tags.\n"
        "Keep it factual and concise.\n"
        f"Section: {section_key}\n"
        f"Page notes:\n{page_notes_json}\n"
    )


def _section_summary_prompt_compact(section_key: str, page_notes_json: str) -> str:
    return (
        "Aggregate page notes into a concise section summary.\n"
        "Return plain text only and keep output compact.\n"
        "Rules:\n"
        '- summary max 120 words\n'
        "- no JSON\n"
        "- no markdown\n"
        f"Section: {section_key}\n"
        f"Page notes:\n{page_notes_json}\n"
    )


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
        # Ensure at least one item goes through even under very tight budgets.
        first = page_notes[0] if isinstance(page_notes[0], dict) else {}
        compact_notes.append(_compact_page_note_for_section(first))
    return _truncate_for_tokens(_json_dumps(compact_notes), max_input_tokens=budget)


def _global_summary_prompt(section_summaries_json: str) -> str:
    return (
        "Aggregate section summaries into a document-level summary.\n"
        "Return plain text only.\n"
        "No JSON and no markdown.\n"
        "First line: one-sentence executive summary.\n"
        "Then a concise multi-sentence summary.\n"
        f"Section summaries:\n{section_summaries_json}\n"
    )


def _global_summary_prompt_compact(section_summaries_json: str) -> str:
    return (
        "Aggregate section summaries into a concise document-level summary.\n"
        "Return plain text only and keep output compact.\n"
        "Rules:\n"
        '- max 160 words total\n'
        "- first line executive summary\n"
        "- no JSON\n"
        "- no markdown\n"
        f"Section summaries:\n{section_summaries_json}\n"
    )


def generate_page_notes(
    settings: Settings,
    *,
    page: int,
    text: str,
) -> dict[str, Any]:
    ensure_text_llm_ready(settings)
    cleaned = _truncate_for_tokens(text, max_input_tokens=6000)
    raw = _chat_response(
        settings,
        prompt=_page_notes_prompt(page, cleaned),
        timeout=settings.page_notes_timeout_seconds,
        max_tokens=settings.page_notes_max_output_tokens,
        json_mode=False,
    )
    sanitized_raw = _sanitize_model_output_text(raw)
    if _looks_like_prompt_echo_or_meta(str(raw or "")) or _looks_like_prompt_echo_or_meta(sanitized_raw):
        logger.warning("Page notes output looks like prompt/meta echo page=%s; retry strict prompt", page)
        retry_raw = _chat_response(
            settings,
            prompt=_page_notes_prompt_strict(page, cleaned),
            timeout=settings.page_notes_timeout_seconds,
            max_tokens=settings.page_notes_max_output_tokens,
            json_mode=False,
        )
        sanitized_raw = _sanitize_model_output_text(retry_raw)
    if not sanitized_raw.strip():
        fallback = _best_effort_page_notes_from_text(page, cleaned)
        fallback["text"] = " ".join(cleaned.split())[:2000]
        return fallback
    parsed = _parse_page_notes_text(page, sanitized_raw)
    parsed["text"] = sanitized_raw
    return parsed


def generate_section_summary(
    settings: Settings,
    *,
    section_key: str,
    page_notes: list[dict[str, Any]],
) -> dict[str, Any]:
    ensure_text_llm_ready(settings)
    payload = _section_notes_to_text(
        page_notes,
        max_input_tokens=settings.section_summary_max_input_tokens,
    )
    if not payload.strip():
        return _best_effort_section_summary(
            section_key=section_key,
            page_notes=page_notes,
            reason="fallback_due_to_empty_page_notes",
        )
    raw = _chat_response(
        settings,
        prompt=_section_summary_prompt(section_key, payload),
        timeout=settings.section_summary_timeout_seconds,
        max_tokens=settings.summary_max_output_tokens,
        json_mode=False,
    )
    summary_text = _sanitize_summary_value(raw, max_chars=2000)
    if not summary_text:
        compact_raw = _chat_response(
            settings,
            prompt=_section_summary_prompt_compact(section_key, payload),
            timeout=settings.section_summary_timeout_seconds,
            max_tokens=max(250, int(settings.summary_max_output_tokens * 0.75)),
            json_mode=False,
        )
        summary_text = _sanitize_summary_value(compact_raw, max_chars=2000)
    if not summary_text:
        return _best_effort_section_summary(
            section_key=section_key,
            page_notes=page_notes,
            reason="fallback_due_to_empty_section_summary_text",
        )
    return _normalize_section_summary_payload(
        section_key,
        {
            "section": section_key,
            "summary": summary_text,
            "key_facts": [],
            "key_dates": [],
            "key_entities": [],
            "key_numbers": [],
            "open_questions": [],
            "confidence_notes": [],
            "text": summary_text,
        },
    )


def generate_global_summary(
    settings: Settings,
    *,
    section_summaries: list[dict[str, Any]],
) -> dict[str, Any]:
    ensure_text_llm_ready(settings)
    section_texts: list[str] = []
    for section in section_summaries:
        if not isinstance(section, dict):
            continue
        section_key = str(section.get("section") or "").strip()
        text = _sanitize_summary_value(section.get("text") or section.get("summary"), max_chars=2000)
        if not text:
            continue
        section_texts.append(f"Section {section_key}: {text}" if section_key else text)
    payload = "\n\n".join(section_texts)
    payload = _truncate_for_tokens(payload, max_input_tokens=settings.global_summary_max_input_tokens)
    if not payload.strip():
        return _best_effort_global_summary(
            section_summaries=section_summaries,
            reason="fallback_due_to_empty_sections_payload",
        )
    raw = _chat_response(
        settings,
        prompt=_global_summary_prompt(payload),
        timeout=settings.global_summary_timeout_seconds,
        max_tokens=settings.summary_max_output_tokens,
        json_mode=False,
    )
    summary_text = _sanitize_summary_value(raw, max_chars=4000)
    if not summary_text:
        compact_raw = _chat_response(
            settings,
            prompt=_global_summary_prompt_compact(payload),
            timeout=settings.global_summary_timeout_seconds,
            max_tokens=max(300, int(settings.summary_max_output_tokens * 0.75)),
            json_mode=False,
        )
        summary_text = _sanitize_summary_value(compact_raw, max_chars=4000)
    if not summary_text:
        return _best_effort_global_summary(
            section_summaries=section_summaries,
            reason="fallback_due_to_empty_global_summary_text",
        )
    lines = [line.strip() for line in summary_text.splitlines() if line.strip()]
    executive = lines[0] if lines else summary_text
    return {
        "summary": summary_text,
        "executive_summary": executive[:320] if executive else "",
        "key_facts": [],
        "key_dates": [],
        "key_entities": [],
        "key_numbers": [],
        "open_questions": [],
        "confidence_notes": [],
    }


def upsert_page_note(
    db: Session,
    *,
    doc_id: int,
    page: int,
    source: str,
    payload: dict[str, Any] | None,
    status: str,
    error: str | None = None,
    model_name: str | None = None,
) -> None:
    db.execute(
        delete(DocumentPageNote).where(
            DocumentPageNote.doc_id == doc_id,
            DocumentPageNote.page == page,
            DocumentPageNote.source == source,
        )
    )
    now = _now_iso()
    db.add(
        DocumentPageNote(
            doc_id=doc_id,
            page=page,
            source=source,
            notes_text=_json_dumps(payload) if payload is not None else None,
            model_name=model_name,
            status=status,
            error=error,
            created_at=now,
            processed_at=now,
        )
    )
    db.commit()


def replace_section_summaries(
    db: Session,
    *,
    doc_id: int,
    source: str,
    summaries: list[tuple[str, dict[str, Any]]],
    model_name: str | None = None,
) -> None:
    db.execute(
        delete(DocumentSectionSummary).where(
            DocumentSectionSummary.doc_id == doc_id,
            DocumentSectionSummary.source == source,
        )
    )
    now = _now_iso()
    for section_key, payload in summaries:
        db.add(
            DocumentSectionSummary(
                doc_id=doc_id,
                section_key=section_key,
                source=source,
                summary_text=_json_dumps(payload),
                model_name=model_name,
                status="ok",
                created_at=now,
                processed_at=now,
            )
        )
    db.commit()


def group_page_ranges(pages: list[int], section_pages: int) -> list[tuple[int, int]]:
    section_pages = max(1, int(section_pages))
    sorted_pages = _sorted_unique_positive_pages(pages)
    if not sorted_pages:
        return []
    ranges: list[tuple[int, int]] = []
    for i in range(0, len(sorted_pages), section_pages):
        chunk = sorted_pages[i : i + section_pages]
        ranges.append((chunk[0], chunk[-1]))
    return ranges


def _sorted_unique_positive_pages(pages: list[int]) -> list[int]:
    return sorted(set(int(page) for page in pages if int(page) > 0))


def group_notes_into_sections(
    notes: list[tuple[int, dict[str, Any]]],
    *,
    max_pages: int,
    max_input_tokens: int,
) -> list[tuple[str, list[dict[str, Any]]]]:
    max_pages = max(1, int(max_pages))
    max_input_tokens = max(1, int(max_input_tokens))
    if not notes:
        return []
    ordered = sorted(notes, key=lambda item: item[0])
    sections: list[tuple[str, list[dict[str, Any]]]] = []
    current_pages: list[int] = []
    current_notes: list[dict[str, Any]] = []
    current_tokens = 0

    def flush() -> None:
        nonlocal current_pages, current_notes, current_tokens
        if not current_pages or not current_notes:
            return
        section_key = f"{current_pages[0]}-{current_pages[-1]}"
        sections.append((section_key, list(current_notes)))
        current_pages = []
        current_notes = []
        current_tokens = 0

    for page, note_payload in ordered:
        note_json = _json_dumps(note_payload)
        note_tokens = estimate_tokens(note_json)
        exceeds_pages = len(current_pages) >= max_pages
        exceeds_tokens = current_tokens + note_tokens > max_input_tokens
        if current_pages and (exceeds_pages or exceeds_tokens):
            flush()
        current_pages.append(int(page))
        current_notes.append(note_payload)
        current_tokens += note_tokens
    flush()
    return sections


def is_large_document(*, page_count: int | None, total_text: str | None, threshold_pages: int) -> bool:
    if page_count and int(page_count) >= threshold_pages:
        return True
    return estimate_tokens(total_text or "") >= max(3000, threshold_pages * 250)


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

    uniq = lambda values: list(dict.fromkeys(v for v in values if v))
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

    uniq = lambda values: list(dict.fromkeys(v for v in values if v))
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
