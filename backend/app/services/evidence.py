from __future__ import annotations

from typing import Any


def resolve_evidence_matches(
    citations: list[dict[str, Any]],
    *,
    max_pages: int = 3,
) -> list[dict[str, Any]]:
    limit = max(1, min(int(max_pages), 5))
    matches: list[dict[str, Any]] = []
    for citation in citations[:limit]:
        doc_id = int(citation.get("doc_id") or 0)
        page = int(citation.get("page") or 0)
        snippet = str(citation.get("snippet") or "").strip()
        bbox = citation.get("bbox")
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
