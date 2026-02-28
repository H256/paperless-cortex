from __future__ import annotations

import os
import json
import logging
from typing import Any
from pathlib import Path
from datetime import datetime

from app.config import Settings
from app.services.ai import llm_client
from app.services.runtime.guard import ensure_text_llm_ready
from app.services.ai.json_extraction import extract_json_object
from app.services.ai.text_budget import truncate_chars

logger = logging.getLogger(__name__)

DEFAULT_PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "suggestions.txt"
_prompt_cache: dict[str, str] = {}

FIELD_PROMPTS = {
    "title": "suggestions_title.txt",
    "date": "suggestions_date.txt",
    "correspondent": "suggestions_correspondent.txt",
    "tags": "suggestions_tags.txt",
    "note": "suggestions_summary.txt",
}


def _is_iso_date(value: str) -> bool:
    try:
        datetime.fromisoformat(value)
        return True
    except Exception:
        return False


def normalize_suggestions_payload(payload: dict[str, Any], known_tags: list[str]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return payload
    # Handle debug wrapper
    if "parsed" in payload and isinstance(payload["parsed"], dict):
        payload["parsed"] = normalize_suggestions_payload(payload["parsed"], known_tags)
        return payload
    data = payload
    title = (data.get("title") or data.get("suggested_title") or "").strip()
    if len(title) > 80:
        title = title[:80].strip()
    correspondent = (data.get("correspondent") or data.get("suggested_correspondent") or "").strip()
    document_type = (data.get("documentType") or data.get("suggested_document_type") or "").strip()
    language = (data.get("language") or "").strip()
    summary = (data.get("summary") or "").strip()
    date_value = (data.get("date") or data.get("suggested_document_date") or "").strip()
    if date_value and not _is_iso_date(date_value):
        date_value = ""

    tags_raw = data.get("tags") or data.get("suggested_tags") or []
    if isinstance(tags_raw, str):
        tags_raw = [t.strip() for t in tags_raw.split(",") if t.strip()]
    tags = []
    for tag in tags_raw:
        if not isinstance(tag, str):
            continue
        cleaned = tag.strip()
        if cleaned and cleaned not in tags:
            tags.append(cleaned)
    tags = tags[:4]

    known_map = {t.lower(): t for t in known_tags}
    tags_existing = []
    tags_new = []
    for tag in tags:
        match = known_map.get(tag.lower())
        if match:
            tags_existing.append(match)
        else:
            tags_new.append(tag)

    data.update(
        {
            "title": title,
            "correspondent": correspondent,
            "documentType": document_type,
            "date": date_value,
            "language": language,
            "summary": summary,
            "tags": tags,
            "suggested_tags_existing": tags_existing,
            "suggested_tags_new": tags_new,
        }
    )
    return data


def _load_prompt(settings: Settings) -> str:
    path = settings.suggestions_prompt_path
    if path:
        configured = Path(path)
        if configured.is_file():
            prompt_path = configured
        else:
            # Allow repo-root relative paths like "backend/app/prompts/suggestions.txt"
            repo_root = Path(__file__).resolve().parents[3]
            repo_relative = repo_root / configured
            prompt_path = repo_relative if repo_relative.is_file() else configured
    else:
        prompt_path = DEFAULT_PROMPT_PATH
    key = str(prompt_path)
    if key in _prompt_cache:
        return _prompt_cache[key]
    if not prompt_path.is_file():
        raise RuntimeError(f"Suggestions prompt file not found: {prompt_path}")
    text = prompt_path.read_text(encoding="utf-8").strip()
    if not text:
        raise RuntimeError(f"Suggestions prompt file empty: {prompt_path}")
    _prompt_cache[key] = text
    logger.info("Loaded suggestions prompt path=%s", prompt_path)
    return text


def _load_field_prompt(field: str) -> str:
    filename = FIELD_PROMPTS.get(field)
    if not filename:
        raise RuntimeError(f"Unsupported suggestion field: {field}")
    prompt_path = Path(__file__).resolve().parents[1] / "prompts" / filename
    key = str(prompt_path)
    if key in _prompt_cache:
        return _prompt_cache[key]
    if not prompt_path.is_file():
        raise RuntimeError(f"Suggestions prompt file not found: {prompt_path}")
    text = prompt_path.read_text(encoding="utf-8").strip()
    if not text:
        raise RuntimeError(f"Suggestions prompt file empty: {prompt_path}")
    _prompt_cache[key] = text
    logger.info("Loaded suggestions field prompt path=%s", prompt_path)
    return text


def generate_suggestions(
    settings: Settings,
    document: dict[str, Any],
    text: str,
    tags: list[str],
    correspondents: list[str],
) -> dict[str, Any]:
    ensure_text_llm_ready(settings)
    doc_meta = {
        "id": document.get("id"),
        "title": document.get("title"),
        "document_date": document.get("document_date"),
        "created": document.get("created"),
        "correspondent": document.get("correspondent"),
        "document_type": document.get("document_type"),
        "tags": document.get("tags"),
    }
    trimmed = truncate_chars(text, settings.suggestions_max_input_chars)
    prompt_template = _load_prompt(settings)
    prompt = (
        prompt_template.replace("{metadata}", json.dumps(doc_meta, ensure_ascii=False))
        .replace("{tags}", json.dumps(tags, ensure_ascii=False))
        .replace("{correspondents}", json.dumps(correspondents, ensure_ascii=False))
        .replace("{text}", trimmed)
    )
    logger.info(
        "Suggestions request model=%s chars=%s doc_id=%s",
        settings.text_model,
        len(trimmed),
        document.get("id"),
    )
    if os.getenv("LLM_DEBUG") == "1":
        logger.info("Suggestions prompt:\n%s", prompt)
    raw_text = llm_client.chat_completion(
        settings,
        model=settings.text_model or "",
        messages=[{"role": "user", "content": prompt}],
        timeout=120,
    )
    logger.info("Suggestions response len=%s", len(raw_text))
    try:
        parsed = extract_json_object(raw_text)
    except Exception as exc:
        logger.warning("Suggestions JSON parse failed: %s", exc)
        parsed = {"raw": raw_text}
    if settings.suggestions_debug:
        parsed = {"raw": raw_text, "parsed": parsed}
    return parsed


def generate_normalized_suggestions(
    settings: Settings,
    document: dict[str, Any],
    text: str,
    *,
    tags: list[str],
    correspondents: list[str],
) -> dict[str, Any]:
    suggestions = generate_suggestions(
        settings,
        document,
        text,
        tags=tags,
        correspondents=correspondents,
    )
    return normalize_suggestions_payload(suggestions, tags)


def generate_field_variants(
    settings: Settings,
    document: dict[str, Any],
    text: str,
    tags: list[str],
    correspondents: list[str],
    field: str,
    count: int,
    current_value: object | None = None,
) -> dict[str, Any]:
    ensure_text_llm_ready(settings)
    doc_meta = {
        "id": document.get("id"),
        "title": document.get("title"),
        "document_date": document.get("document_date"),
        "created": document.get("created"),
        "correspondent": document.get("correspondent"),
        "document_type": document.get("document_type"),
        "tags": document.get("tags"),
    }
    trimmed = truncate_chars(text, settings.suggestions_max_input_chars)
    prompt_template = _load_field_prompt(field)
    prompt = (
        prompt_template.replace("{metadata}", json.dumps(doc_meta, ensure_ascii=False))
        .replace("{tags}", json.dumps(tags, ensure_ascii=False))
        .replace("{correspondents}", json.dumps(correspondents, ensure_ascii=False))
        .replace("{text}", trimmed)
        .replace("{count}", str(count))
        .replace("{current}", json.dumps(current_value, ensure_ascii=False))
    )
    logger.info(
        "Suggestions field request model=%s field=%s count=%s doc_id=%s",
        settings.text_model,
        field,
        count,
        document.get("id"),
    )
    if os.getenv("LLM_DEBUG") == "1":
        logger.info("Suggestions field prompt:\n%s", prompt)
    raw_text = llm_client.chat_completion(
        settings,
        model=settings.text_model or "",
        messages=[{"role": "user", "content": prompt}],
        timeout=120,
    )
    logger.info("Suggestions field response len=%s", len(raw_text))
    try:
        parsed = extract_json_object(raw_text)
    except Exception as exc:
        logger.warning("Suggestions field JSON parse failed: %s", exc)
        parsed = {"raw": raw_text}
    if settings.suggestions_debug:
        parsed = {"raw": raw_text, "parsed": parsed}
    return parsed


