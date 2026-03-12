from __future__ import annotations

from typing import Any

AI_SUMMARY_MARKER = "KI-Zusammenfassung"


def normalize_scalar(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_tags(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []
    normalized: list[int] = []
    for item in value:
        try:
            normalized.append(int(item))
        except (TypeError, ValueError):
            continue
    return sorted(set(normalized))


def extract_ai_summary_note(notes: list[dict[str, Any]] | None) -> tuple[int | None, str | None]:
    if not notes:
        return None, None
    for note in notes:
        raw_text = str(note.get("note") or "")
        if raw_text.strip().endswith(AI_SUMMARY_MARKER):
            note_id = note.get("id")
            try:
                if isinstance(note_id, int):
                    return note_id, raw_text
                if isinstance(note_id, str):
                    return int(note_id), raw_text
                return None, raw_text
            except (TypeError, ValueError):
                return None, raw_text
    return None, None


def canonical_ai_summary(note_text: str | None) -> str:
    if not note_text:
        return ""
    lines = [line.rstrip() for line in str(note_text).splitlines()]
    while lines and not lines[-1].strip():
        lines.pop()
    if lines and lines[-1].strip() == AI_SUMMARY_MARKER:
        lines.pop()
    while lines and not lines[-1].strip():
        lines.pop()
    if lines:
        last = lines[-1].strip().lower()
        if "model:" in last or "created:" in last:
            lines.pop()
    while lines and not lines[-1].strip():
        lines.pop()
    body = "\n".join(lines).strip()
    return " ".join(body.split())


def compare_document_fields(
    *,
    local_title: str | None,
    remote_title: str | None,
    local_date: str | None,
    remote_date: str | None,
    local_correspondent_id: int | None,
    remote_correspondent_id: int | None,
    local_pending_correspondent_name: str | None = None,
    local_tags: list[int],
    remote_tags: list[int],
    local_pending_tag_names: list[str] | None = None,
    local_ai_note: str | None,
    remote_ai_note: str | None,
) -> tuple[list[str], dict[str, Any]]:
    changed: list[str] = []
    payload: dict[str, Any] = {}

    if normalize_scalar(local_title) != normalize_scalar(remote_title):
        changed.append("title")
        payload["title"] = normalize_scalar(local_title) or None
    if normalize_scalar(local_date) != normalize_scalar(remote_date):
        changed.append("issue_date")
        payload["created"] = normalize_scalar(local_date) or None
    pending_correspondent_name = normalize_scalar(local_pending_correspondent_name)
    if (local_correspondent_id or None) != (remote_correspondent_id or None) or bool(pending_correspondent_name):
        changed.append("correspondent")
        payload["correspondent"] = local_correspondent_id
        payload["pending_correspondent_name"] = pending_correspondent_name or None
    pending_tag_names = [str(name).strip() for name in (local_pending_tag_names or []) if str(name).strip()]
    if normalize_tags(local_tags) != normalize_tags(remote_tags) or bool(pending_tag_names):
        changed.append("tags")
        payload["tags"] = normalize_tags(local_tags)
        payload["pending_tag_names"] = sorted(set(pending_tag_names), key=str.lower)

    local_summary = canonical_ai_summary(local_ai_note)
    remote_summary = canonical_ai_summary(remote_ai_note)
    if local_summary:
        if local_summary != remote_summary:
            changed.append("note")
            payload["note"] = local_ai_note
            payload["note_action"] = "replace" if remote_ai_note else "add"
        else:
            payload["note_action"] = "unchanged"
    else:
        payload["note_action"] = "none"

    return changed, payload
