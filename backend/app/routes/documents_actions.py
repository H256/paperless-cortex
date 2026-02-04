from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import get_db
from app.deps import get_settings
from app.models import Document, DocumentEmbedding, DocumentPageText, DocumentSuggestion
from app.services.queue import enqueue_task_sequence
from app.services.embeddings import delete_points_for_doc
from app.api_models import (
    ClearIntelligenceResponse,
    DeleteEmbeddingsResponse,
    DeleteSuggestionsResponse,
    DeleteVisionOcrResponse,
    ProcessMissingResponse,
    ResetIntelligenceResponse,
)
from app.routes.documents_common import parse_iso, should_skip_doc

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/process-missing", response_model=ProcessMissingResponse)
def process_missing(
    dry_run: bool = False,
    include_vision_ocr: bool = True,
    include_embeddings: bool = True,
    include_suggestions_paperless: bool = True,
    include_suggestions_vision: bool = True,
    embeddings_mode: str = "auto",
    limit: int | None = None,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    if not settings.queue_enabled:
        return {"enabled": False, "docs": 0, "enqueued": 0, "tasks": 0, "dry_run": dry_run}
    if embeddings_mode not in ("auto", "paperless", "vision"):
        raise HTTPException(status_code=400, detail="Invalid embeddings_mode")
    if limit is not None and limit < 1:
        raise HTTPException(status_code=400, detail="limit must be >= 1")

    docs = db.query(Document).order_by(Document.id.asc()).all()
    if include_vision_ocr:
        docs.sort(
            key=lambda doc: (
                doc.page_count is None,
                doc.page_count or 0,
                doc.id,
            )
        )
    embeddings = {row.doc_id: row for row in db.query(DocumentEmbedding).all()}
    suggestions = {(row.doc_id, row.source): row for row in db.query(DocumentSuggestion).all()}
    vision_rows = (
        db.query(DocumentPageText)
        .filter(DocumentPageText.source == "vision_ocr")
        .all()
    )
    vision_latest: dict[int, datetime] = {}
    for row in vision_rows:
        created = parse_iso(row.created_at)
        if not created:
            continue
        current = vision_latest.get(row.doc_id)
        if current is None or created > current:
            vision_latest[row.doc_id] = created

    enqueued_docs = 0
    enqueued_tasks = 0
    missing_docs = 0
    missing_vision = 0
    missing_embeddings = 0
    missing_embeddings_vision = 0
    missing_sugg_p = 0
    missing_sugg_v = 0
    selected_for_run = 0
    for doc in docs:
        if should_skip_doc(doc):
            continue
        tasks: list[dict] = []
        doc_modified = parse_iso(doc.modified) or parse_iso(doc.created)
        embedding = embeddings.get(doc.id)
        embedded_at = parse_iso(embedding.embedded_at) if embedding else None
        embedding_source = embedding.embedding_source if embedding else None
        has_vision_embedding = embedding_source == "vision"
        vision_updated_at = vision_latest.get(doc.id)
        sugg_p = suggestions.get((doc.id, "paperless_ocr"))
        sugg_v = suggestions.get((doc.id, "vision_ocr"))
        sugg_p_at = parse_iso(sugg_p.created_at) if sugg_p else None
        sugg_v_at = parse_iso(sugg_v.created_at) if sugg_v else None
        needs_vision = include_vision_ocr and (not vision_updated_at or (doc_modified and vision_updated_at < doc_modified))
        needs_embeddings = include_embeddings and (
            not embedded_at
            or (doc_modified and embedded_at < doc_modified)
            or (embeddings_mode == "vision" and not has_vision_embedding)
        )
        needs_embeddings_vision = include_embeddings and embeddings_mode == "vision" and not has_vision_embedding
        needs_sugg_p = include_suggestions_paperless and (
            not sugg_p_at or (doc_modified and sugg_p_at < doc_modified)
        )
        needs_sugg_v = include_suggestions_vision and (
            not sugg_v_at or (doc_modified and sugg_v_at < doc_modified)
        )
        if needs_vision:
            missing_vision += 1
            tasks.append({"doc_id": doc.id, "task": "vision_ocr"})
        if needs_embeddings:
            missing_embeddings += 1
            if embeddings_mode == "vision":
                tasks.append({"doc_id": doc.id, "task": "embeddings_vision"})
            elif embeddings_mode == "paperless":
                tasks.append({"doc_id": doc.id, "task": "embeddings_paperless"})
            else:
                tasks.append(
                    {
                        "doc_id": doc.id,
                        "task": "embeddings_vision" if settings.enable_vision_ocr else "embeddings_paperless",
                    }
                )
        if needs_embeddings_vision:
            missing_embeddings_vision += 1
        if needs_sugg_p:
            missing_sugg_p += 1
            tasks.append({"doc_id": doc.id, "task": "suggestions_paperless"})
        if needs_sugg_v:
            missing_sugg_v += 1
            tasks.append({"doc_id": doc.id, "task": "suggestions_vision"})
        if tasks:
            missing_docs += 1
        if limit is not None and selected_for_run >= limit:
            continue
        if tasks:
            selected_for_run += 1
            if not dry_run:
                enqueued_docs += 1
                enqueued_tasks += enqueue_task_sequence(settings, tasks)

    return {
        "enabled": True,
        "docs": missing_docs,
        "missing_vision": missing_vision,
        "missing_embeddings": missing_embeddings,
        "missing_vision_embeddings": missing_embeddings_vision,
        "missing_suggestions_paperless": missing_sugg_p,
        "missing_suggestions_vision": missing_sugg_v,
        "selected": selected_for_run,
        "enqueued": enqueued_docs,
        "tasks": enqueued_tasks,
        "dry_run": dry_run,
    }


@router.post("/reset-intelligence", response_model=ResetIntelligenceResponse)
def reset_intelligence(
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    if not settings.queue_enabled:
        return {"enabled": False}
    db.execute(delete(DocumentSuggestion))
    db.execute(delete(DocumentPageText))
    db.execute(delete(DocumentEmbedding))
    db.commit()
    return {"enabled": True}


@router.post("/clear-intelligence", response_model=ClearIntelligenceResponse)
def clear_intelligence(
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    if not settings.queue_enabled:
        return {"enabled": False}
    db.execute(delete(DocumentSuggestion))
    db.execute(delete(DocumentPageText))
    db.execute(delete(DocumentEmbedding))
    db.commit()
    return {"enabled": True}


@router.post("/delete/vision-ocr", response_model=DeleteVisionOcrResponse)
def delete_vision_ocr(
    doc_id: int | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(DocumentPageText).filter(DocumentPageText.source == "vision_ocr")
    if doc_id is not None:
        query = query.filter(DocumentPageText.doc_id == doc_id)
    count = query.count()
    query.delete(synchronize_session=False)
    db.commit()
    return {"deleted": count}


@router.post("/delete/suggestions", response_model=DeleteSuggestionsResponse)
def delete_suggestions(
    doc_id: int | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(DocumentSuggestion)
    if doc_id is not None:
        query = query.filter(DocumentSuggestion.doc_id == doc_id)
    count = query.count()
    query.delete(synchronize_session=False)
    db.commit()
    return {"deleted": count}


@router.post("/delete/embeddings", response_model=DeleteEmbeddingsResponse)
def delete_embeddings(
    doc_id: int | None = None,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    if doc_id is not None:
        delete_points_for_doc(settings, doc_id)
        row = db.get(DocumentEmbedding, doc_id)
        if row:
            db.delete(row)
            db.commit()
        return {"deleted": 1}
    db.query(DocumentEmbedding).delete(synchronize_session=False)
    db.commit()
    return {"deleted": 1}
