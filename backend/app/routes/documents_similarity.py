from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, selectinload

from app.api_models import SimilarDocumentsResponse, SimilarMetadata, SimilarMetadataResponse
from app.db import get_db
from app.deps import get_settings
from app.models import Correspondent, Document, Tag
from app.services.documents.read_models import apply_derived_fields_and_review_status
from app.services.integrations import paperless
from app.services.search.similarity import (
    aggregate_similar_metadata,
    fetch_doc_point_vector,
    search_similar_doc_points,
)

if TYPE_CHECKING:
    from app.config import Settings

router = APIRouter(prefix="/documents", tags=["documents"])
logger = logging.getLogger(__name__)


def _build_document_summary_payload(
    settings: Settings,
    db: Session,
    doc_ids: list[int],
) -> dict[int, dict]:
    if not doc_ids:
        return {}
    try:
        remote_docs_by_id = paperless.get_documents_cached(settings, doc_ids)
    except (RuntimeError, httpx.HTTPError):
        remote_docs_by_id = {}
    docs = (
        db.query(Document)
        .options(
            selectinload(Document.tags).load_only(Tag.id),
            selectinload(Document.correspondent).load_only(Correspondent.name),
        )
        .filter(Document.id.in_(doc_ids))
        .all()
    )
    base_results = []
    for doc in docs:
        remote_doc = remote_docs_by_id.get(int(doc.id), {})
        remote_correspondent_id = remote_doc.get("correspondent")
        correspondent_name = doc.correspondent.name if doc.correspondent else None
        if remote_correspondent_id not in (None, doc.correspondent_id):
            correspondent_name = None
        base_results.append(
            {
                "id": doc.id,
                "title": remote_doc.get("title") or doc.title,
                "document_date": remote_doc.get("document_date") or doc.document_date,
                "created": remote_doc.get("created") or doc.created,
                "modified": remote_doc.get("modified") or doc.modified,
                "correspondent": remote_correspondent_id
                if isinstance(remote_correspondent_id, int | str)
                else doc.correspondent_id,
                "correspondent_name": correspondent_name,
                "document_type": remote_doc.get("document_type") or doc.document_type_id,
                "tags": (
                    [int(tag_id) for tag_id in remote_doc.get("tags", []) if isinstance(tag_id, int)]
                    if isinstance(remote_doc.get("tags"), list)
                    else [tag.id for tag in doc.tags]
                ),
                "notes": remote_doc.get("notes") if isinstance(remote_doc.get("notes"), list) else [],
            }
        )
    payload: dict[str, object] = {
        "count": len(base_results),
        "next": None,
        "previous": None,
        "results": base_results,
    }
    enriched = apply_derived_fields_and_review_status(
        payload=payload,
        db=db,
        include_derived=True,
        include_summary_preview=True,
        review_status="all",
        page=1,
        page_size=max(1, len(base_results)),
    )
    enriched_results = enriched.get("results", [])
    results = [
        row for row in enriched_results if isinstance(row, dict)
    ] if isinstance(enriched_results, list) else []
    return {
        int(row_id): row
        for row in results
        if isinstance((row_id := row.get("id")), int | str)
    }


@router.get("/{doc_id}/similar", response_model=SimilarDocumentsResponse)
def get_similar_documents(
    doc_id: int,
    top_k: int = Query(default=10, ge=1, le=50),
    min_score: float | None = Query(default=None, ge=0.0),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    vector = fetch_doc_point_vector(settings, doc_id)
    if not vector:
        raise HTTPException(status_code=404, detail="Doc embedding not found")
    matches = search_similar_doc_points(settings, vector, top_k=top_k + 1, min_score=min_score)
    filtered = [item for item in matches if int(item["doc_id"]) != int(doc_id)]
    filtered = filtered[:top_k]
    doc_ids = [int(item["doc_id"]) for item in filtered]
    summaries = _build_document_summary_payload(settings, db, doc_ids)
    results = [
        {
            "doc_id": int(item["doc_id"]),
            "score": float(item.get("score") or 0.0),
            "document": summaries.get(int(item["doc_id"])),
        }
        for item in filtered
    ]
    return {"doc_id": doc_id, "top_k": top_k, "matches": results}


@router.get("/{doc_id}/duplicates", response_model=SimilarDocumentsResponse)
def get_duplicate_documents(
    doc_id: int,
    threshold: float = Query(default=0.92, ge=0.0, le=1.0),
    top_k: int = Query(default=10, ge=1, le=50),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    vector = fetch_doc_point_vector(settings, doc_id)
    if not vector:
        raise HTTPException(status_code=404, detail="Doc embedding not found")
    matches = search_similar_doc_points(settings, vector, top_k=top_k + 1, min_score=threshold)
    filtered = [item for item in matches if int(item["doc_id"]) != int(doc_id)]
    filtered = filtered[:top_k]
    doc_ids = [int(item["doc_id"]) for item in filtered]
    summaries = _build_document_summary_payload(settings, db, doc_ids)
    results = [
        {
            "doc_id": int(item["doc_id"]),
            "score": float(item.get("score") or 0.0),
            "document": summaries.get(int(item["doc_id"])),
        }
        for item in filtered
    ]
    return {"doc_id": doc_id, "top_k": top_k, "matches": results}


@router.get("/{doc_id}/similar-metadata", response_model=SimilarMetadataResponse)
def get_similar_metadata(
    doc_id: int,
    top_k: int = Query(default=10, ge=1, le=50),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    vector = fetch_doc_point_vector(settings, doc_id)
    if not vector:
        raise HTTPException(status_code=404, detail="Doc embedding not found")
    matches = search_similar_doc_points(settings, vector, top_k=top_k + 1, min_score=None)
    filtered = [item for item in matches if int(item["doc_id"]) != int(doc_id)]
    filtered = filtered[:top_k]
    doc_ids = [int(item["doc_id"]) for item in filtered]
    score_by_doc = {int(item["doc_id"]): float(item.get("score") or 0.0) for item in filtered}
    if not doc_ids:
        return {"doc_id": doc_id, "top_k": top_k, "metadata": SimilarMetadata()}

    metadata_payload = aggregate_similar_metadata(db, doc_ids=doc_ids, score_by_doc=score_by_doc)
    metadata = SimilarMetadata(**metadata_payload)
    return {"doc_id": doc_id, "top_k": top_k, "metadata": metadata}
