from __future__ import annotations

from typing import Any

from app.config import Settings
from app.services import llm_client
from app.services.guard import ensure_text_llm_ready
from app.services.hierarchical_helpers import (
    _best_effort_global_summary,
    _best_effort_page_notes_from_text,
    _best_effort_section_summary,
    _extract_json_dict,
    _looks_like_prompt_echo_or_meta,
    _normalize_section_summary_payload,
    _parse_page_notes_text,
    _sanitize_model_output_text,
    _sanitize_summary_value,
    _section_notes_to_text,
    _truncate_for_tokens,
)


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
        "- Preserve the original document language(s); do not translate to English.\n"
        "- If the source is multilingual, keep each extracted point in its original language.\n"
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
        "Preserve the original document language(s); do not translate.\n"
        f"Page: {page}\n"
        f"Text:\n{text}\n"
    )


def _section_summary_prompt(section_key: str, page_notes_json: str) -> str:
    return (
        "Aggregate page notes into a concise section summary.\n"
        "Return plain text only.\n"
        "No JSON, no markdown, no XML/control tags.\n"
        "Keep it factual and concise.\n"
        "Preserve the original document language(s); do not translate.\n"
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
        "- preserve the original document language(s); do not translate\n"
        f"Section: {section_key}\n"
        f"Page notes:\n{page_notes_json}\n"
    )


def _global_summary_prompt(section_summaries_json: str) -> str:
    return (
        "Aggregate section summaries into a document-level summary.\n"
        "Return plain text only.\n"
        "No JSON and no markdown.\n"
        "First line: one-sentence executive summary.\n"
        "Then a concise multi-sentence summary.\n"
        "Preserve the original document language(s); do not translate.\n"
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
        "- preserve the original document language(s); do not translate\n"
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
