from __future__ import annotations

import logging
from typing import Any

import httpx
from sqlalchemy.orm import Session, joinedload

from app.models import Document, Tag, Correspondent, DocumentType

from app.config import Settings
from app.services.search import qdrant
from app.services.search.embeddings import make_doc_point_id, search_points

logger = logging.getLogger(__name__)


def fetch_doc_point_vector(settings: Settings, doc_id: int) -> list[float] | None:
    point_id = make_doc_point_id(doc_id)
    try:
        payload = qdrant.retrieve_points(settings, [point_id], with_vector=True, with_payload=False)
    except httpx.HTTPStatusError as exc:
        # Treat missing collection/points as "no vector yet" so API returns 404 instead of 500.
        if exc.response.status_code == 404:
            logger.info("Doc-level vector not found in Qdrant for doc_id=%s", doc_id)
            return None
        raise
    results = payload.get("result", []) if isinstance(payload, dict) else []
    if not results:
        return None
    vector = results[0].get("vector") if isinstance(results[0], dict) else None
    if isinstance(vector, dict):
        vector = vector.get("default")
    if not isinstance(vector, list):
        return None
    return [float(value) for value in vector if isinstance(value, (int, float))]


def search_similar_doc_points(
    settings: Settings,
    vector: list[float],
    *,
    top_k: int,
    min_score: float | None = None,
) -> list[dict[str, Any]]:
    raw = search_points(
        settings,
        vector,
        limit=max(1, top_k),
        filter_payload={"must": [{"key": "type", "match": {"value": "doc"}}]},
        score_threshold=min_score,
    )
    hits = raw.get("result", []) or []
    results: list[dict[str, Any]] = []
    for hit in hits:
        payload = hit.get("payload") or {}
        doc_id = payload.get("doc_id")
        if doc_id is None:
            continue
        results.append(
            {
                "doc_id": int(doc_id),
                "score": float(hit.get("score") or 0.0),
            }
        )
    return results


def aggregate_similar_metadata(
    db: Session,
    *,
    doc_ids: list[int],
    score_by_doc: dict[int, float],
) -> dict[str, Any]:
    if not doc_ids:
        return {"tags": [], "correspondent": None, "documentType": None, "language": None}
    docs = (
        db.query(Document)
        .options(
            joinedload(Document.tags).load_only(Tag.name),
            joinedload(Document.correspondent).load_only(Correspondent.name),
            joinedload(Document.document_type).load_only(DocumentType.name),
        )
        .filter(Document.id.in_(doc_ids))
        .all()
    )
    title_weights: dict[str, float] = {}
    tag_weights: dict[str, float] = {}
    correspondent_weights: dict[str, float] = {}
    doc_type_weights: dict[str, float] = {}
    for doc in docs:
        score = score_by_doc.get(int(doc.id), 0.0)
        if doc.title:
            title_weights[str(doc.title)] = title_weights.get(str(doc.title), 0.0) + score
        for tag in doc.tags:
            if tag.name:
                tag_weights[str(tag.name)] = tag_weights.get(str(tag.name), 0.0) + score
        if doc.correspondent and doc.correspondent.name:
            key = str(doc.correspondent.name)
            correspondent_weights[key] = correspondent_weights.get(key, 0.0) + score
        if doc.document_type and doc.document_type.name:
            key = str(doc.document_type.name)
            doc_type_weights[key] = doc_type_weights.get(key, 0.0) + score

    top_title = next(iter(sorted(title_weights.items(), key=lambda item: item[1], reverse=True)), None)
    sorted_tags = [name for name, _ in sorted(tag_weights.items(), key=lambda item: item[1], reverse=True)]
    top_corr = next(iter(sorted(correspondent_weights.items(), key=lambda item: item[1], reverse=True)), None)
    top_doc_type = next(iter(sorted(doc_type_weights.items(), key=lambda item: item[1], reverse=True)), None)
    return {
        "title": top_title[0] if top_title else None,
        "tags": sorted_tags[:4],
        "correspondent": top_corr[0] if top_corr else None,
        "documentType": top_doc_type[0] if top_doc_type else None,
        "language": None,
    }
