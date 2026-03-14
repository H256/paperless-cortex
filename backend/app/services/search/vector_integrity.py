from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from app.models import Document, DocumentEmbedding
from app.services.search import vector_store
from app.services.search.embeddings import make_point_id

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.config import Settings

RetrievePointsFn = Callable[..., dict[str, Any]]


def _expected_sources(embedding_source: str | None) -> list[str]:
    normalized = str(embedding_source or "").strip().lower()
    if normalized == "both":
        return ["vision", "paperless"]
    if normalized in {"vision", "vision_ocr"}:
        return ["vision"]
    if normalized in {"paperless", "paperless_ocr"}:
        return ["paperless"]
    return []


def _count_found_vectors(
    settings: Settings,
    *,
    doc_id: int,
    chunk_count: int,
    sources: list[str],
    retrieve_points_fn: RetrievePointsFn,
    batch_size: int,
) -> tuple[int, int]:
    found_vectors = 0
    expected_vectors = 0
    for source in sources:
        point_ids = [make_point_id(doc_id, chunk, source) for chunk in range(chunk_count)]
        expected_vectors += len(point_ids)
        for start in range(0, len(point_ids), batch_size):
            payload = retrieve_points_fn(
                settings,
                point_ids[start : start + batch_size],
                with_vector=True,
                with_payload=False,
            )
            rows = payload.get("result", []) if isinstance(payload, dict) else []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                vector = row.get("vector")
                if isinstance(vector, list) and vector:
                    found_vectors += 1
    return expected_vectors, found_vectors


def audit_missing_vector_chunks(
    settings: Settings,
    db: Session,
    *,
    limit: int = 100,
    batch_size: int = 128,
    retrieve_points_fn: RetrievePointsFn | None = None,
) -> dict[str, Any]:
    retrieve_points = retrieve_points_fn or vector_store.retrieve_points
    normalized_limit = max(1, int(limit))
    scanned_docs = 0
    affected_docs = 0
    fully_missing_docs = 0
    partial_missing_docs = 0
    items: list[dict[str, Any]] = []

    rows = (
        db.query(DocumentEmbedding, Document.title)
        .join(Document, Document.id == DocumentEmbedding.doc_id)
        .filter(DocumentEmbedding.chunk_count.isnot(None), DocumentEmbedding.chunk_count > 0)
        .order_by(DocumentEmbedding.doc_id.asc())
        .all()
    )

    for embedding, title in rows:
        sources = _expected_sources(embedding.embedding_source)
        if not sources:
            continue
        chunk_count = int(embedding.chunk_count or 0)
        if chunk_count <= 0:
            continue
        scanned_docs += 1
        expected_vectors, found_vectors = _count_found_vectors(
            settings,
            doc_id=int(embedding.doc_id),
            chunk_count=chunk_count,
            sources=sources,
            retrieve_points_fn=retrieve_points,
            batch_size=batch_size,
        )
        if found_vectors >= expected_vectors:
            continue
        affected_docs += 1
        fully_missing = found_vectors == 0
        if fully_missing:
            fully_missing_docs += 1
        else:
            partial_missing_docs += 1
        if len(items) < normalized_limit:
            items.append(
                {
                    "doc_id": int(embedding.doc_id),
                    "title": str(title) if title is not None else None,
                    "embedding_source": embedding.embedding_source,
                    "chunk_count": chunk_count,
                    "expected_vectors": expected_vectors,
                    "found_vectors": found_vectors,
                    "fully_missing": fully_missing,
                    "embedded_at": embedding.embedded_at,
                }
            )

    return {
        "provider": str(settings.vector_store.provider or "unknown"),
        "scanned_docs": scanned_docs,
        "affected_docs": affected_docs,
        "fully_missing_docs": fully_missing_docs,
        "partial_missing_docs": partial_missing_docs,
        "limit": normalized_limit,
        "truncated": affected_docs > normalized_limit,
        "items": items,
    }
