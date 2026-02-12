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


def _section_summary_prompt(section_key: str, page_notes_json: str) -> str:
    return (
        "Aggregate page notes into a section summary.\n"
        "Return only valid JSON.\n"
        "Schema:\n"
        '{ "section": "<key>", "summary": string, "key_facts": [string], "key_dates": [string], "key_entities": [string], "key_numbers": [string], "open_questions": [string], "confidence_notes": [string] }\n'
        f"Section: {section_key}\n"
        f"Page notes JSON:\n{page_notes_json}\n"
    )


def _section_summary_prompt_compact(section_key: str, page_notes_json: str) -> str:
    return (
        "Aggregate page notes into a concise section summary.\n"
        "Return only valid JSON and keep output compact.\n"
        "Rules:\n"
        '- summary max 120 words\n'
        '- each list max 6 entries\n'
        "- do not include markdown or prose outside JSON\n"
        "Schema:\n"
        '{ "section": "<key>", "summary": string, "key_facts": [string], "key_dates": [string], "key_entities": [string], "key_numbers": [string], "open_questions": [string], "confidence_notes": [string] }\n'
        f"Section: {section_key}\n"
        f"Page notes JSON:\n{page_notes_json}\n"
    )


def _global_summary_prompt(section_summaries_json: str) -> str:
    return (
        "Aggregate section summaries into a document-level summary.\n"
        "Return only valid JSON.\n"
        "Schema:\n"
        '{ "summary": string, "executive_summary": string, "key_facts": [string], "key_dates": [string], "key_entities": [string], "key_numbers": [string], "open_questions": [string], "confidence_notes": [string] }\n'
        f"Section summaries JSON:\n{section_summaries_json}\n"
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
    if not str(raw or "").strip():
        return _best_effort_page_notes_from_text(page, cleaned)
    try:
        parsed = _extract_json_dict(raw)
        return _coerce_page_notes_payload(page, parsed, raw_fallback=raw)
    except Exception as exc:
        if os.getenv("LLM_DEBUG") == "1":
            logger.warning(
                "Page notes JSON parse failed page=%s error=%s raw_snippet=%s",
                page,
                exc,
                _raw_preview(raw),
            )
        return _parse_page_notes_text(page, raw)


def generate_section_summary(
    settings: Settings,
    *,
    section_key: str,
    page_notes: list[dict[str, Any]],
) -> dict[str, Any]:
    ensure_text_llm_ready(settings)
    payload = _json_dumps(page_notes)
    payload = _truncate_for_tokens(payload, max_input_tokens=settings.section_summary_max_input_tokens)
    try:
        parsed = _chat_json_response(
            settings,
            prompt=_section_summary_prompt(section_key, payload),
            timeout=settings.section_summary_timeout_seconds,
            max_tokens=settings.summary_max_output_tokens,
        )
        parsed["section"] = section_key
        return parsed
    except Exception as exc:
        logger.warning("Section summary primary parse failed section=%s error=%s", section_key, exc)
        try:
            compact_raw = _chat_response(
                settings,
                prompt=_section_summary_prompt_compact(section_key, payload),
                timeout=settings.section_summary_timeout_seconds,
                max_tokens=max(250, int(settings.summary_max_output_tokens * 0.75)),
                json_mode=False,
            )
            parsed = _extract_json_dict(compact_raw)
            parsed["section"] = section_key
            return parsed
        except Exception as retry_exc:
            logger.warning(
                "Section summary compact retry failed section=%s error=%s",
                section_key,
                retry_exc,
            )
            return _best_effort_section_summary(
                section_key=section_key,
                page_notes=page_notes,
                reason=f"fallback_due_to_json_parse_error:{retry_exc}",
            )


def generate_global_summary(
    settings: Settings,
    *,
    section_summaries: list[dict[str, Any]],
) -> dict[str, Any]:
    ensure_text_llm_ready(settings)
    payload = _json_dumps(section_summaries)
    payload = _truncate_for_tokens(payload, max_input_tokens=settings.global_summary_max_input_tokens)
    return _chat_json_response(
        settings,
        prompt=_global_summary_prompt(payload),
        timeout=settings.global_summary_timeout_seconds,
        max_tokens=settings.summary_max_output_tokens,
    )


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
            notes_json=_json_dumps(payload) if payload is not None else None,
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
                summary_json=_json_dumps(payload),
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
                text = str(item).strip()
                if text:
                    facts.append(text)
                    dates.extend(_DATE_TOKEN_RE.findall(text))
                    numbers.extend(_NUMBER_TOKEN_RE.findall(text))
        note_entities = note.get("entities") if isinstance(note, dict) else []
        if isinstance(note_entities, list):
            for item in note_entities:
                text = str(item).strip()
                if text:
                    entities.append(text)
        note_numbers = note.get("key_numbers") if isinstance(note, dict) else []
        if isinstance(note_numbers, list):
            for item in note_numbers:
                text = str(item).strip()
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
    return {
        "section": section_key,
        "summary": summary,
        "key_facts": facts_u,
        "key_dates": dates_u,
        "key_entities": entities_u,
        "key_numbers": numbers_u,
        "open_questions": [],
        "confidence_notes": [reason],
    }
