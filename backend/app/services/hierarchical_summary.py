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
_BULLET_PREFIX_RE = re.compile(r"^(?:[-*]|\u2022|\d+[.)])\s*")
_NUMBER_TOKEN_RE = re.compile(
    r"\b(?:\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?(?:\s?(?:EUR|USD|CHF|%))?|\d{4}-\d{2}-\d{2})\b"
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
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(raw[start : end + 1])
    raise ValueError("No JSON object found in response")


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
    result = {
        "page": int(page),
        "facts": _normalize_list(payload.get("facts")),
        "entities": _normalize_list(payload.get("entities")),
        "references": _normalize_list(payload.get("references")),
        "key_numbers": _normalize_list(payload.get("key_numbers")),
        "uncertainties": _normalize_list(payload.get("uncertainties")),
    }
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
    section_aliases = {
        "facts": ("facts", "fakten"),
        "entities": ("entities", "entitaeten"),
        "references": ("references", "referenzen", "belege"),
        "key_numbers": ("key numbers", "key_numbers", "zahlen", "kennzahlen"),
        "uncertainties": ("uncertainties", "unsicherheiten"),
    }
    heading_to_key: dict[str, str] = {}
    for key, aliases in section_aliases.items():
        for alias in aliases:
            heading_to_key[alias] = key

    values: dict[str, list[str]] = {
        "facts": [],
        "entities": [],
        "references": [],
        "key_numbers": [],
        "uncertainties": [],
    }
    current_key: str | None = None
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        heading = line.rstrip(":").strip().lower()
        resolved = heading_to_key.get(heading)
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
    raw = llm_client.chat_completion(
        settings,
        model=settings.text_model or "",
        messages=[{"role": "user", "content": _page_notes_prompt(page, cleaned)}],
        timeout=settings.page_notes_timeout_seconds,
        max_tokens=settings.page_notes_max_output_tokens,
        temperature=0.0,
        json_mode=False,
    )
    if not str(raw or "").strip():
        return _best_effort_page_notes_from_text(page, cleaned)
    try:
        parsed = _extract_json_dict(raw)
        return _coerce_page_notes_payload(page, parsed, raw_fallback=raw)
    except Exception as exc:
        if os.getenv("LLM_DEBUG") == "1":
            preview = str(raw or "").replace("\n", "\\n")
            if len(preview) > 500:
                preview = preview[:500] + "...<truncated>"
            logger.warning(
                "Page notes JSON parse failed page=%s error=%s raw_snippet=%s",
                page,
                exc,
                preview,
            )
        return _parse_page_notes_text(page, raw)


def generate_section_summary(
    settings: Settings,
    *,
    section_key: str,
    page_notes: list[dict[str, Any]],
) -> dict[str, Any]:
    ensure_text_llm_ready(settings)
    payload = json.dumps(page_notes, ensure_ascii=False)
    payload = _truncate_for_tokens(payload, max_input_tokens=settings.section_summary_max_input_tokens)
    raw = llm_client.chat_completion(
        settings,
        model=settings.text_model or "",
        messages=[{"role": "user", "content": _section_summary_prompt(section_key, payload)}],
        timeout=settings.section_summary_timeout_seconds,
        max_tokens=settings.summary_max_output_tokens,
        temperature=0.0,
        json_mode=True,
    )
    parsed = _extract_json_dict(raw)
    parsed["section"] = section_key
    return parsed


def generate_global_summary(
    settings: Settings,
    *,
    section_summaries: list[dict[str, Any]],
) -> dict[str, Any]:
    ensure_text_llm_ready(settings)
    payload = json.dumps(section_summaries, ensure_ascii=False)
    payload = _truncate_for_tokens(payload, max_input_tokens=settings.global_summary_max_input_tokens)
    raw = llm_client.chat_completion(
        settings,
        model=settings.text_model or "",
        messages=[{"role": "user", "content": _global_summary_prompt(payload)}],
        timeout=settings.global_summary_timeout_seconds,
        max_tokens=settings.summary_max_output_tokens,
        temperature=0.0,
        json_mode=True,
    )
    return _extract_json_dict(raw)


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
            notes_json=json.dumps(payload, ensure_ascii=False) if payload is not None else None,
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
                summary_json=json.dumps(payload, ensure_ascii=False),
                model_name=model_name,
                status="ok",
                created_at=now,
                processed_at=now,
            )
        )
    db.commit()


def group_page_ranges(pages: list[int], section_pages: int) -> list[tuple[int, int]]:
    if not pages:
        return []
    sorted_pages = sorted(set(int(page) for page in pages if int(page) > 0))
    ranges: list[tuple[int, int]] = []
    for i in range(0, len(sorted_pages), section_pages):
        chunk = sorted_pages[i : i + section_pages]
        ranges.append((chunk[0], chunk[-1]))
    return ranges


def group_notes_into_sections(
    notes: list[tuple[int, dict[str, Any]]],
    *,
    max_pages: int,
    max_input_tokens: int,
) -> list[tuple[str, list[dict[str, Any]]]]:
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
        note_json = json.dumps(note_payload, ensure_ascii=False)
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
