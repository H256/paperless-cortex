from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from datetime import datetime, timezone
from hashlib import sha256
import logging
from sqlalchemy.orm import Session

from app.config import Settings, load_settings
from app.db import get_db
from app.models import Document, DocumentEmbedding, SyncState, Correspondent
from app.services.embeddings import (
    chunk_document_with_pages,
    delete_points_for_doc,
    embed_text,
    ensure_qdrant_collection,
    make_point_id,
    search_points,
    upsert_points,
)
from app.services.text_pages import get_page_text_layers
from app.services import paperless
from app.services.page_text_store import upsert_page_texts

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
        content_value = doc.content or ""
        logger.info("Embedding doc=%s fetching page-aware text", doc.id)
        baseline_pages, vision_pages = get_page_text_layers(
            settings,
            doc.content,
            fetch_pdf_bytes=lambda: paperless.get_document_pdf(settings, doc.id),
            force_full_vision=bool(force),
        )
        if vision_pages:
            upsert_page_texts(db, settings, doc.id, vision_pages, source_filter="vision_ocr")
        page_texts = baseline_pages + vision_pages
        if not content_value and not page_texts:
            processed += 1
            state.processed = processed
            continue
        if page_texts:
            hash_source = "\f".join(f"{page.source}:{page.text}" for page in page_texts)
        else:
            hash_source = content_value
        content_hash = sha256((hash_source or "").encode("utf-8")).hexdigest()
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
        baseline_chunks = chunk_document_with_pages(settings, content_value, baseline_pages or None)
        vision_chunks = chunk_document_with_pages(settings, content_value, vision_pages or None) if vision_pages else []
        chunks = baseline_chunks + vision_chunks
        logger.info("Embedding doc=%s chunks=%s page_texts=%s", doc.id, len(chunks), len(page_texts))
        doc_points = []
        for idx, chunk in enumerate(chunks):
            chunk_text_value = str(chunk["text"])
            vector = embed_text(settings, chunk_text_value)
            doc_points.append(
                {
                    "id": make_point_id(doc.id, idx),
                    "vector": vector,
                    "payload": {
                        "doc_id": doc.id,
                        "chunk": idx,
                        "text": chunk_text_value,
                        "page": chunk.get("page"),
                        "source": chunk.get("source"),
                        "quality_score": chunk.get("quality_score"),
                    },
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
        content_value = doc.content or ""
        logger.info("Embedding doc=%s fetching page-aware text", doc.id)
        baseline_pages, vision_pages = get_page_text_layers(
            settings,
            doc.content,
            fetch_pdf_bytes=lambda: paperless.get_document_pdf(settings, doc.id),
            force_full_vision=bool(force),
        )
        if vision_pages:
            upsert_page_texts(db, settings, doc.id, vision_pages, source_filter="vision_ocr")
        page_texts = baseline_pages + vision_pages
        if not content_value and not page_texts:
            processed += 1
            state.processed = processed
            continue
        if page_texts:
            hash_source = "\f".join(f"{page.source}:{page.text}" for page in page_texts)
        else:
            hash_source = content_value
        content_hash = sha256((hash_source or "").encode("utf-8")).hexdigest()
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
        baseline_chunks = chunk_document_with_pages(settings, content_value, baseline_pages or None)
        vision_chunks = chunk_document_with_pages(settings, content_value, vision_pages or None) if vision_pages else []
        chunks = baseline_chunks + vision_chunks
        logger.info("Embedding doc=%s chunks=%s page_texts=%s", doc.id, len(chunks), len(page_texts))
        doc_points = []
        for idx, chunk in enumerate(chunks):
            chunk_text_value = str(chunk["text"])
            vector = embed_text(settings, chunk_text_value)
            doc_points.append(
                {
                    "id": make_point_id(doc.id, idx),
                    "vector": vector,
                    "payload": {
                        "doc_id": doc.id,
                        "chunk": idx,
                        "text": chunk_text_value,
                        "page": chunk.get("page"),
                        "source": chunk.get("source"),
                        "quality_score": chunk.get("quality_score"),
                    },
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
    dedupe: bool = True,
    rerank: bool = True,
    source: str | None = None,
    min_quality: int | None = None,
    include_doc: bool = True,
    settings: Settings = Depends(settings_dep),
    db: Session = Depends(get_db),
):
    logger.info(
        "Search q=%s top_k=%s dedupe=%s rerank=%s source=%s include_doc=%s",
        q,
        top_k,
        dedupe,
        rerank,
        source,
        include_doc,
    )
    vector = embed_text(settings, q)
    raw = search_points(settings, vector, limit=top_k)
    hits = raw.get("result", []) or []
    results = []
    for hit in hits:
        payload = hit.get("payload") or {}
        if source and payload.get("source") != source:
            continue
        text = str(payload.get("text") or "")
        snippet = text[:240]
        quality_score = payload.get("quality_score")
        if quality_score is None:
            quality_score = 100
        if min_quality is not None and quality_score < min_quality:
            continue
        results.append(
            {
                "doc_id": payload.get("doc_id"),
                "page": payload.get("page"),
                "snippet": snippet,
                "score": hit.get("score"),
                "source": payload.get("source"),
                "quality_score": quality_score,
                "bbox": payload.get("bbox"),
            }
        )
    if not dedupe:
        matches = results
    else:
        deduped: dict[tuple[object, object], dict[str, object]] = {}
        for item in results:
            key = (item.get("doc_id"), item.get("page"))
            current = deduped.get(key)
            if not current:
                deduped[key] = item
                continue
            if rerank:
                current_score = float(current.get("score") or 0) * (
                    float(current.get("quality_score") or 100) / 100.0
                )
                next_score = float(item.get("score") or 0) * (
                    float(item.get("quality_score") or 100) / 100.0
                )
                if next_score > current_score:
                    deduped[key] = item
            else:
                if (item.get("score") or 0) > (current.get("score") or 0):
                    deduped[key] = item
        matches = list(deduped.values())
    if rerank:
        matches.sort(
            key=lambda item: float(item.get("score") or 0)
            * (float(item.get("quality_score") or 100) / 100.0),
            reverse=True,
        )
    else:
        matches.sort(key=lambda item: float(item.get("score") or 0), reverse=True)
    if include_doc and matches:
        doc_ids = {item.get("doc_id") for item in matches if item.get("doc_id") is not None}
        if doc_ids:
            docs = db.query(Document).filter(Document.id.in_(list(doc_ids))).all()
            docs_by_id = {
                doc.id: {
                    "id": doc.id,
                    "title": doc.title,
                    "document_date": doc.document_date,
                    "created": doc.created,
                    "correspondent_id": doc.correspondent_id,
                }
                for doc in docs
            }
            corr_ids = {doc.correspondent_id for doc in docs if doc.correspondent_id}
            correspondents = {}
            if corr_ids:
                rows = db.query(Correspondent).filter(Correspondent.id.in_(list(corr_ids))).all()
                correspondents = {row.id: row.name for row in rows}
            for item in matches:
                doc = docs_by_id.get(item.get("doc_id"))
                if doc and doc.get("correspondent_id"):
                    doc["correspondent_name"] = correspondents.get(doc.get("correspondent_id"))
                item["document"] = doc
    logger.info("Search matches=%s", len(matches))
    return {"query": q, "top_k": top_k, "matches": matches}


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
