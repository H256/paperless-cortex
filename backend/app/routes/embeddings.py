from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from datetime import datetime, timezone
from hashlib import sha256
import logging
from sqlalchemy.orm import Session

from app.config import Settings, load_settings
from app.db import get_db
from app.models import Document, DocumentEmbedding, SyncState
from app.services.embeddings import (
    chunk_text,
    delete_points_for_doc,
    embed_text,
    ensure_qdrant_collection,
    make_point_id,
    search_points,
    upsert_points,
)

router = APIRouter(prefix="/embeddings", tags=["embeddings"])
logger = logging.getLogger(__name__)


def settings_dep() -> Settings:
    return load_settings()


@router.post("/ingest")
def ingest_embeddings(
    doc_id: int | None = Query(default=None),
    limit: int = Query(default=100),
    force: bool = Query(default=False),
    settings: Settings = Depends(settings_dep),
    db: Session = Depends(get_db),
):
    state = db.get(SyncState, "embeddings")
    if not state:
        state = SyncState(key="embeddings")
        db.add(state)
    state.status = "running"
    state.started_at = datetime.now(timezone.utc).isoformat()
    state.processed = 0
    state.total = 0
    state.cancel_requested = False
    db.commit()
    logger.info("Embedding ingest started doc_id=%s limit=%s force=%s", doc_id, limit, force)

    query = db.query(Document)
    if doc_id is not None:
        query = query.filter(Document.id == doc_id)
    if limit <= 0:
        documents = query.all()
    else:
        documents = query.limit(limit).all()
    if not documents:
        state.status = "idle"
        state.last_synced_at = datetime.now(timezone.utc).isoformat()
        db.commit()
        return {"ingested": 0, "documents_embedded": 0}

    sample_embedding = embed_text(settings, "dimension probe")
    ensure_qdrant_collection(settings, vector_size=len(sample_embedding))

    points = []
    embedded = 0
    processed = 0
    state.total = len(documents)
    db.commit()
    for doc in documents:
        db.refresh(state)
        if state.cancel_requested:
            state.status = "cancelled"
            db.commit()
            return {"ingested": 0, "documents_embedded": embedded, "status": "cancelled"}
        if not doc.content:
            processed += 1
            state.processed = processed
            continue
        content_hash = sha256(doc.content.encode("utf-8")).hexdigest()
        existing = db.get(DocumentEmbedding, doc.id)
        if not force and existing:
            if (
                existing.content_hash == content_hash
                and existing.embedding_model == settings.embedding_model
                and existing.chunk_count
            ):
                logger.info("Skip embed doc=%s (unchanged)", doc.id)
                processed += 1
                state.processed = processed
                if processed % 5 == 0 or processed == state.total:
                    db.commit()
                continue
        delete_points_for_doc(settings, doc.id)
        chunks = chunk_text(settings, doc.content)
        doc_points = []
        for idx, chunk in enumerate(chunks):
            vector = embed_text(settings, chunk)
            doc_points.append(
                {
                    "id": make_point_id(doc.id, idx),
                    "vector": vector,
                    "payload": {"doc_id": doc.id, "chunk": idx, "text": chunk},
                }
            )
            if idx % 5 == 0 or idx == len(chunks) - 1:
                logger.info("Embedding doc=%s chunk=%s/%s", doc.id, idx + 1, len(chunks))
        if doc_points:
            logger.info("Upserting doc=%s points=%s", doc.id, len(doc_points))
            upsert_points(settings, doc_points)
            points.extend(doc_points)
        else:
            logger.info("Skipping doc=%s (no chunks)", doc.id)
        if not existing:
            existing = DocumentEmbedding(doc_id=doc.id)
            db.add(existing)
        existing.content_hash = content_hash
        existing.embedding_model = settings.embedding_model
        existing.embedded_at = datetime.now(timezone.utc).isoformat()
        existing.chunk_count = len(chunks)
        embedded += 1
        processed += 1
        state.processed = processed
        if processed % 5 == 0 or processed == state.total:
            logger.info("Embedding progress %s/%s", processed, state.total)
            db.commit()
    if points:
        db.commit()
    state.status = "idle"
    state.last_synced_at = datetime.now(timezone.utc).isoformat()
    db.commit()
    logger.info("Embedding ingest finished embedded=%s points=%s", embedded, len(points))
    return {"ingested": len(points), "documents_embedded": embedded}


@router.post("/ingest-docs")
def ingest_documents(
    doc_ids: list[int],
    force: bool = Query(default=False),
    settings: Settings = Depends(settings_dep),
    db: Session = Depends(get_db),
):
    documents = db.query(Document).filter(Document.id.in_(doc_ids)).all()
    if not documents:
        return {"ingested": 0, "documents_embedded": 0}
    sample_embedding = embed_text(settings, "dimension probe")
    ensure_qdrant_collection(settings, vector_size=len(sample_embedding))
    state = db.get(SyncState, "embeddings")
    if not state:
        state = SyncState(key="embeddings")
        db.add(state)
    state.status = "running"
    state.started_at = datetime.now(timezone.utc).isoformat()
    state.processed = 0
    state.total = len(documents)
    state.cancel_requested = False
    db.commit()
    logger.info("Embedding ingest-docs started count=%s force=%s", len(documents), force)

    points = []
    embedded = 0
    processed = 0
    for doc in documents:
        db.refresh(state)
        if state.cancel_requested:
            state.status = "cancelled"
            db.commit()
            return {"ingested": 0, "documents_embedded": embedded, "status": "cancelled"}
        if not doc.content:
            processed += 1
            state.processed = processed
            continue
        content_hash = sha256(doc.content.encode("utf-8")).hexdigest()
        existing = db.get(DocumentEmbedding, doc.id)
        if not force and existing:
            if (
                existing.content_hash == content_hash
                and existing.embedding_model == settings.embedding_model
                and existing.chunk_count
            ):
                logger.info("Skip embed doc=%s (unchanged)", doc.id)
                processed += 1
                state.processed = processed
                if processed % 5 == 0 or processed == state.total:
                    db.commit()
                continue
        delete_points_for_doc(settings, doc.id)
        chunks = chunk_text(settings, doc.content)
        doc_points = []
        for idx, chunk in enumerate(chunks):
            vector = embed_text(settings, chunk)
            doc_points.append(
                {
                    "id": make_point_id(doc.id, idx),
                    "vector": vector,
                    "payload": {"doc_id": doc.id, "chunk": idx, "text": chunk},
                }
            )
            if idx % 5 == 0 or idx == len(chunks) - 1:
                logger.info("Embedding doc=%s chunk=%s/%s", doc.id, idx + 1, len(chunks))
        if doc_points:
            logger.info("Upserting doc=%s points=%s", doc.id, len(doc_points))
            upsert_points(settings, doc_points)
            points.extend(doc_points)
        else:
            logger.info("Skipping doc=%s (no chunks)", doc.id)
        if not existing:
            existing = DocumentEmbedding(doc_id=doc.id)
            db.add(existing)
        existing.content_hash = content_hash
        existing.embedding_model = settings.embedding_model
        existing.embedded_at = datetime.now(timezone.utc).isoformat()
        existing.chunk_count = len(chunks)
        embedded += 1
        processed += 1
        state.processed = processed
        if processed % 5 == 0 or processed == state.total:
            logger.info("Embedding progress %s/%s", processed, state.total)
            db.commit()
    if points:
        db.commit()
    state.status = "idle"
    state.last_synced_at = datetime.now(timezone.utc).isoformat()
    db.commit()
    logger.info("Embedding ingest-docs finished embedded=%s points=%s", embedded, len(points))
    return {"ingested": len(points), "documents_embedded": embedded}


@router.get("/search")
def search(
    q: str,
    top_k: int = 5,
    settings: Settings = Depends(settings_dep),
):
    vector = embed_text(settings, q)
    return search_points(settings, vector, limit=top_k)


@router.get("/status")
def embedding_status(db: Session = Depends(get_db)):
    state = db.get(SyncState, "embeddings")
    if not state:
        return {"status": "idle", "processed": 0, "total": 0, "started_at": None}
    eta_seconds = None
    if state.started_at and state.processed and state.total:
        try:
            started = datetime.fromisoformat(state.started_at.replace("Z", "+00:00"))
            elapsed = (datetime.now(timezone.utc) - started).total_seconds()
            rate = state.processed / max(1.0, elapsed)
            remaining = state.total - state.processed
            eta_seconds = int(max(0.0, remaining / rate)) if rate > 0 else None
        except Exception:
            eta_seconds = None
    return {
        "status": state.status or "idle",
        "processed": state.processed or 0,
        "total": state.total or 0,
        "started_at": state.started_at,
        "last_synced_at": state.last_synced_at,
        "cancel_requested": state.cancel_requested or False,
        "eta_seconds": eta_seconds,
    }


@router.post("/cancel")
def cancel_embeddings(db: Session = Depends(get_db)):
    state = db.get(SyncState, "embeddings")
    if not state:
        return {"status": "idle"}
    state.cancel_requested = True
    db.commit()
    return {"status": "cancelling"}
