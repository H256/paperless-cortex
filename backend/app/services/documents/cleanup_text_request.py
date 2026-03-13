from __future__ import annotations

from typing import TypedDict

ALLOWED_CLEANUP_SOURCES = {"paperless_ocr", "vision_ocr", "pdf_text"}


class CleanupTextRequestPayload(TypedDict):
    doc_ids: list[int]
    source: str | None
    clear_first: bool
    enqueue: bool


def build_cleanup_text_request_payload(
    *,
    doc_ids: list[int] | None,
    source: str | None,
    clear_first: bool,
    enqueue: bool,
) -> CleanupTextRequestPayload:
    if source and source not in ALLOWED_CLEANUP_SOURCES:
        raise ValueError("Invalid source")
    return {
        "doc_ids": [int(doc_id) for doc_id in (doc_ids or []) if int(doc_id) > 0],
        "source": source,
        "clear_first": clear_first,
        "enqueue": enqueue,
    }
