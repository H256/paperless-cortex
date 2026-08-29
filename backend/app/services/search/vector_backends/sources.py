"""Shared mapping between embedding source names and stored payload values.

Chunk payloads store the raw page source (e.g. ``paperless_ocr``, ``pdf_text``,
``vision_ocr``) while pipeline callers pass the normalized embedding source
(``paperless`` / ``vision``). This module is the single source of truth for
translating between the two so source-scoped deletes match stored points.
"""

from __future__ import annotations


def normalize_embedding_source(source: str | None) -> str | None:
    if not source:
        return None
    normalized = str(source).strip().lower()
    if normalized in {"paperless", "paperless_ocr"}:
        return "paperless"
    if normalized in {"vision", "vision_ocr"}:
        return "vision"
    return normalized


def embedding_source_payload_values(source: str | None) -> str | tuple[str, ...] | None:
    """Map an embedding source to the stored chunk payload source value(s).

    Returns ``None`` when no source restriction applies, a single string when
    exactly one stored payload value matches, or a tuple when a normalized
    source spans several stored payload values (``paperless``).
    """
    normalized = normalize_embedding_source(source)
    if normalized is None:
        return None
    if normalized == "paperless":
        return ("paperless_ocr", "pdf_text")
    if normalized == "vision":
        return "vision_ocr"
    return normalized
