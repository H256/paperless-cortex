from __future__ import annotations

from typing import Any

from app.services.ai import hierarchical_generation as _gen
from app.services.runtime.guard import ensure_text_llm_ready
from app.services.ai.hierarchical_helpers import (
    _best_effort_global_summary,
    _best_effort_page_notes_from_text,
    _best_effort_section_summary,
    _coerce_page_notes_payload,
    _compact_page_note_for_section,
    _compact_page_notes_for_section,
    _compact_text_items,
    _extract_json_dict,
    _is_summary_meta_text,
    _json_dumps,
    _looks_like_prompt_echo_or_meta,
    _normalize_heading,
    _normalize_list,
    _normalize_section_summary_payload,
    _page_note_payload_to_text,
    _parse_page_notes_text,
    _raw_preview,
    _sanitize_model_output_text,
    _sanitize_summary_list,
    _sanitize_summary_value,
    _section_notes_to_text,
    _truncate_for_tokens,
)
from app.services.ai.hierarchical_storage import (
    _sorted_unique_positive_pages,
    group_notes_into_sections,
    group_page_ranges,
    is_large_document,
    replace_section_summaries,
    upsert_page_note,
)

_GEN_CHAT_RESPONSE = _gen._chat_response
_GEN_CHAT_JSON_RESPONSE = _gen._chat_json_response


def _chat_response(
    settings,
    *,
    prompt: str,
    timeout: int,
    max_tokens: int,
    json_mode: bool,
) -> str:
    return _GEN_CHAT_RESPONSE(
        settings,
        prompt=prompt,
        timeout=timeout,
        max_tokens=max_tokens,
        json_mode=json_mode,
    )


def _chat_json_response(
    settings,
    *,
    prompt: str,
    timeout: int,
    max_tokens: int,
) -> dict[str, Any]:
    return _GEN_CHAT_JSON_RESPONSE(
        settings,
        prompt=prompt,
        timeout=timeout,
        max_tokens=max_tokens,
    )


def _sync_generation_overrides() -> None:
    # Preserve monkeypatch compatibility for tests that patch symbols on this module.
    _gen.ensure_text_llm_ready = ensure_text_llm_ready
    _gen._chat_response = _chat_response
    _gen._chat_json_response = _chat_json_response


def generate_page_notes(settings, *, page: int, text: str) -> dict[str, Any]:
    _sync_generation_overrides()
    return _gen.generate_page_notes(settings, page=page, text=text)


def generate_section_summary(
    settings,
    *,
    section_key: str,
    page_notes: list[dict[str, Any]],
) -> dict[str, Any]:
    _sync_generation_overrides()
    return _gen.generate_section_summary(
        settings,
        section_key=section_key,
        page_notes=page_notes,
    )


def generate_global_summary(
    settings,
    *,
    section_summaries: list[dict[str, Any]],
) -> dict[str, Any]:
    _sync_generation_overrides()
    return _gen.generate_global_summary(
        settings,
        section_summaries=section_summaries,
    )


__all__ = [
    "_best_effort_global_summary",
    "_best_effort_page_notes_from_text",
    "_best_effort_section_summary",
    "_chat_json_response",
    "_chat_response",
    "_coerce_page_notes_payload",
    "_compact_page_note_for_section",
    "_compact_page_notes_for_section",
    "_compact_text_items",
    "_extract_json_dict",
    "_is_summary_meta_text",
    "_json_dumps",
    "_looks_like_prompt_echo_or_meta",
    "_normalize_heading",
    "_normalize_list",
    "_normalize_section_summary_payload",
    "_page_note_payload_to_text",
    "_parse_page_notes_text",
    "_raw_preview",
    "_sanitize_model_output_text",
    "_sanitize_summary_list",
    "_sanitize_summary_value",
    "_section_notes_to_text",
    "_sorted_unique_positive_pages",
    "_truncate_for_tokens",
    "ensure_text_llm_ready",
    "generate_global_summary",
    "generate_page_notes",
    "generate_section_summary",
    "group_notes_into_sections",
    "group_page_ranges",
    "is_large_document",
    "replace_section_summaries",
    "upsert_page_note",
]
