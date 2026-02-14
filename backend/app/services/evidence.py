from __future__ import annotations

import logging
from typing import Any

from app.config import Settings

logger = logging.getLogger(__name__)


def _normalize_source(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"paperless_ocr", "paperless"}:
        return "paperless"
    if raw in {"vision_ocr", "vision"}:
        return "vision"
    return raw


def _normalize_bbox(raw: Any) -> list[float] | None:
    if not isinstance(raw, list) or len(raw) != 4:
        return None
    try:
        x0, y0, x1, y1 = [float(value) for value in raw]
    except Exception:
        return None
    if not (x1 > x0 and y1 > y0):
        return None
    return [x0, y0, x1, y1]


def _resolve_bbox_from_vector_hits(
    settings: Settings,
    *,
    doc_id: int,
    page: int,
    snippet: str,
    source: str | None = None,
) -> tuple[list[float] | None, float]:
    if not settings.evidence_vector_lookup_enabled:
        return None, 0.0
    if not settings.embedding_model or not settings.qdrant_url:
        return None, 0.0
    try:
        from app.services.embeddings import embed_text, search_points

        vector = embed_text(settings, snippet)
        raw = search_points(settings, vector, limit=25)
    except Exception as exc:
        logger.warning("Evidence vector lookup failed doc=%s page=%s error=%s", doc_id, page, exc)
        return None, 0.0
    normalized_source = _normalize_source(source)
    best_bbox: list[float] | None = None
    best_score = 0.0
    for hit in (raw.get("result") or []):
        payload = hit.get("payload") or {}
        if int(payload.get("doc_id") or 0) != doc_id:
            continue
        if int(payload.get("page") or 0) != page:
            continue
        payload_source = _normalize_source(payload.get("source"))
        if normalized_source and payload_source and payload_source != normalized_source:
            continue
        bbox = _normalize_bbox(payload.get("bbox"))
        if bbox is None:
            continue
        score = float(hit.get("score") or 0.0)
        if score > best_score:
            best_bbox = bbox
            best_score = score
    return best_bbox, best_score


def resolve_evidence_matches(
    citations: list[dict[str, Any]],
    *,
    max_pages: int = 3,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    limit = max(1, min(int(max_pages), 5))
    matches: list[dict[str, Any]] = []
    seen_pages: set[tuple[int, int]] = set()
    resolved_cache: dict[tuple[int, int, str, str], tuple[list[float] | None, float]] = {}
    for citation in citations:
        doc_id = int(citation.get("doc_id") or 0)
        page = int(citation.get("page") or 0)
        page_key = (doc_id, page)
        if page_key not in seen_pages:
            if len(seen_pages) >= limit:
                continue
            seen_pages.add(page_key)
        snippet = str(citation.get("snippet") or "").strip()
        bbox = _normalize_bbox(citation.get("bbox"))
        if doc_id <= 0 or page <= 0:
            matches.append(
                {
                    "doc_id": max(doc_id, 0),
                    "page": max(page, 0),
                    "snippet": snippet,
                    "bbox": None,
                    "confidence": 0.0,
                    "status": "error",
                    "error": "invalid_doc_or_page",
                }
            )
            continue
        if bbox is not None:
            matches.append(
                {
                    "doc_id": doc_id,
                    "page": page,
                    "snippet": snippet,
                    "bbox": bbox,
                    "confidence": 1.0,
                    "status": "ok",
                    "error": None,
                }
            )
            continue
        if citation.get("bbox") is not None:
            matches.append(
                {
                    "doc_id": doc_id,
                    "page": page,
                    "snippet": snippet,
                    "bbox": None,
                    "confidence": 0.0,
                    "status": "error",
                    "error": "invalid_bbox",
                }
            )
            continue
        if not snippet:
            matches.append(
                {
                    "doc_id": doc_id,
                    "page": page,
                    "snippet": snippet,
                    "bbox": None,
                    "confidence": 0.0,
                    "status": "error",
                    "error": "empty_snippet",
                }
            )
            continue
        matched_bbox: list[float] | None = None
        matched_score = 0.0
        if settings is not None:
            source = str(citation.get("source") or "").strip() or None
            cache_key = (doc_id, page, _normalize_source(source), snippet)
            cached = resolved_cache.get(cache_key)
            if cached is None:
                cached = _resolve_bbox_from_vector_hits(
                    settings,
                    doc_id=doc_id,
                    page=page,
                    snippet=snippet,
                    source=source,
                )
                resolved_cache[cache_key] = cached
            matched_bbox, matched_score = cached
        if matched_bbox is not None:
            matches.append(
                {
                    "doc_id": doc_id,
                    "page": page,
                    "snippet": snippet,
                    "bbox": matched_bbox,
                    "confidence": max(0.0, min(1.0, matched_score)),
                    "status": "ok",
                    "error": None,
                }
            )
            continue
        matches.append(
            {
                "doc_id": doc_id,
                "page": page,
                "snippet": snippet,
                "bbox": None,
                "confidence": 0.0,
                "status": "no_match",
                "error": None,
            }
        )
    return matches
