from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from typing import TYPE_CHECKING, Any

from app.models import DocumentPageAnchor
from app.services.documents.documents import fetch_pdf_bytes

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.config import Settings


def _norm_token(value: str) -> str:
    token = re.sub(r"[^\w]+", "", (value or "").strip().lower(), flags=re.UNICODE)
    return token


def _tokenize_text(value: str) -> list[str]:
    return [token for token in (_norm_token(part) for part in (value or "").split()) if token]


def _normalize_bbox(raw: Any) -> list[float] | None:
    if not isinstance(raw, list) or len(raw) != 4:
        return None
    try:
        x0, y0, x1, y1 = [float(value) for value in raw]
    except (TypeError, ValueError):
        return None
    if not (x1 > x0 and y1 > y0):
        return None
    return [x0, y0, x1, y1]


def _match_snippet_to_words(words: list[dict[str, Any]], snippet: str) -> tuple[list[float] | None, float]:
    snippet_tokens = _tokenize_text(snippet)
    if len(snippet_tokens) < 2:
        return None, 0.0

    page_tokens: list[str] = []
    for word in words:
        token = _norm_token(str(word.get("text") or ""))
        if token:
            page_tokens.append(token)
        else:
            page_tokens.append("")

    token_count = len(snippet_tokens)
    if len(page_tokens) < token_count:
        return None, 0.0

    snippet_joined = " ".join(snippet_tokens)
    best_score = 0.0
    best_range: tuple[int, int] | None = None
    for start in range(0, len(page_tokens) - token_count + 1):
        window_tokens = page_tokens[start : start + token_count]
        if not window_tokens or any(not token for token in window_tokens):
            continue
        equal_hits = sum(1 for idx, token in enumerate(snippet_tokens) if window_tokens[idx] == token)
        score = equal_hits / token_count
        if score >= 1.0:
            best_score = 1.0
            best_range = (start, start + token_count)
            break
        if score > best_score:
            best_score = score
            best_range = (start, start + token_count)
            continue
        if score < 0.6:
            continue
        ratio = SequenceMatcher(None, snippet_joined, " ".join(window_tokens)).ratio()
        if ratio > best_score:
            best_score = ratio
            best_range = (start, start + token_count)

    if not best_range or best_score < 0.72:
        return None, 0.0

    start, end = best_range
    matched = [word for word in words[start:end] if _normalize_bbox(word.get("bbox")) is not None]
    if not matched:
        return None, 0.0
    bboxes: list[list[float]] = [
        bbox
        for word in matched
        for bbox in [_normalize_bbox(word.get("bbox"))]
        if bbox is not None
    ]
    if not bboxes:
        return None, 0.0
    x0 = min(bbox[0] for bbox in bboxes)
    y0 = min(bbox[1] for bbox in bboxes)
    x1 = max(bbox[2] for bbox in bboxes)
    y1 = max(bbox[3] for bbox in bboxes)
    return [x0, y0, x1, y1], best_score


def _load_page_words(
    settings: Settings,
    doc_id: int,
    page: int,
    pdf_cache: dict[int, bytes],
    words_cache: dict[tuple[int, int], list[dict[str, Any]]],
    db: Session | None = None,
) -> list[dict[str, Any]]:
    cache_key = (doc_id, page)
    cached = words_cache.get(cache_key)
    if cached is not None:
        return cached
    if db is not None:
        row = db.get(DocumentPageAnchor, (int(doc_id), int(page), "paperless_pdf"))
        if row:
            if str(row.status or "") == "no_text_layer":
                words_cache[cache_key] = []
                return []
            raw = str(row.anchors_json or "").strip()
            if raw:
                try:
                    payload = json.loads(raw)
                    if isinstance(payload, list):
                        restored: list[dict[str, Any]] = []
                        for item in payload:
                            if not isinstance(item, dict):
                                continue
                            bbox = _normalize_bbox(item.get("bbox"))
                            text = str(item.get("text") or "").strip()
                            if bbox is None or not text:
                                continue
                            restored.append({"text": text, "bbox": bbox})
                        words_cache[cache_key] = restored
                        return restored
                except json.JSONDecodeError:
                    pass
    pdf_bytes = pdf_cache.get(doc_id)
    if pdf_bytes is None:
        pdf_bytes = fetch_pdf_bytes(settings, doc_id)
        pdf_cache[doc_id] = pdf_bytes
    import fitz  # pymupdf

    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    page_index = max(0, page - 1)
    if page_index >= document.page_count:
        words_cache[cache_key] = []
        return []
    page_obj = document[page_index]
    raw_words = page_obj.get_text("words", sort=True) or []
    words: list[dict[str, Any]] = []
    for raw in raw_words:
        if len(raw) < 5:
            continue
        bbox = _normalize_bbox([raw[0], raw[1], raw[2], raw[3]])
        if bbox is None:
            continue
        words.append({"text": str(raw[4] or ""), "bbox": bbox})
    words_cache[cache_key] = words
    return words


def resolve_evidence_matches(
    citations: list[dict[str, Any]],
    *,
    max_pages: int = 3,
    settings: Settings | None = None,
    db: Session | None = None,
) -> list[dict[str, Any]]:
    limit = max(1, min(int(max_pages), 5))
    matches: list[dict[str, Any]] = []
    seen_pages: set[tuple[int, int]] = set()
    pdf_cache: dict[int, bytes] = {}
    words_cache: dict[tuple[int, int], list[dict[str, Any]]] = {}
    resolved_cache: dict[tuple[int, int, str], tuple[list[float] | None, float]] = {}
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
        if settings is not None:
            cache_key = (doc_id, page, snippet)
            resolved = resolved_cache.get(cache_key)
            if resolved is None:
                try:
                    words = _load_page_words(settings, doc_id, page, pdf_cache, words_cache, db=db)
                    resolved = _match_snippet_to_words(words, snippet)
                except (RuntimeError, ValueError, OSError):
                    resolved = (None, 0.0)
                resolved_cache[cache_key] = resolved
            resolved_bbox, resolved_score = resolved
            if resolved_bbox is not None:
                matches.append(
                    {
                        "doc_id": doc_id,
                        "page": page,
                        "snippet": snippet,
                        "bbox": resolved_bbox,
                        "confidence": max(0.0, min(1.0, resolved_score)),
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
