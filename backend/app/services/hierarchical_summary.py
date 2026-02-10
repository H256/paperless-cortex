from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import DocumentPageNote, DocumentSectionSummary
from app.services import llm_client
from app.services.guard import ensure_text_llm_ready
from app.services.text_cleaning import estimate_tokens


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_json_dict(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("{") and raw.endswith("}"):
        return json.loads(raw)
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(raw[start : end + 1])
    raise ValueError("No JSON object found in response")


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
        "Return only valid JSON.\n"
        "Schema:\n"
        '{ "page": <int>, "facts": [string], "entities": [string], "references": [string], "key_numbers": [string], "uncertainties": [string] }\n'
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
    )
    parsed = _extract_json_dict(raw)
    parsed["page"] = int(page)
    return parsed


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
