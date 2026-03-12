from __future__ import annotations

import logging
import re
from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
from typing import TYPE_CHECKING

from app.config import Settings
from app.models import Correspondent, Document, DocumentEmbedding, SyncState
from app.services.pipeline.sync_state import ensure_started, get_or_create_state, mark_running
from app.services.runtime.time_utils import estimate_eta_seconds

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

ResponseDict = dict[str, object]
ChunkPayload = dict[str, object]
PointPayload = dict[str, object]
QueueEnqueuer = Callable[[Settings, dict[str, object]], object]
QueueStatsFn = Callable[[Settings], dict[str, int] | None]
CollectPageTextsFn = Callable[..., tuple[list[object], list[object], list[object]]]
EnsureEmbeddingCollectionFn = Callable[[Settings], object]
ChunkDocumentFn = Callable[..., list[ChunkPayload]]
DeletePointsFn = Callable[[Settings, int, str], object]
EmbedTextFn = Callable[[Settings, str], list[float]]
MakePointIdFn = Callable[[int, int, str | None], int | str]
MakeDocPointIdFn = Callable[[int], int | str]
UpsertPointsFn = Callable[[Settings, list[PointPayload]], object]
SearchPointsFn = Callable[..., dict[str, object]]


def coerce_int(value: object, default: int = 0) -> int:
    return value if isinstance(value, int) else default


def coerce_float(value: object, default: float = 0.0) -> float:
    return float(value) if isinstance(value, int | float) else default


def coerce_doc_id(value: object) -> int | None:
    return value if isinstance(value, int) else None


def enqueue_embedding_tasks(
    settings: Settings,
    db: Session,
    documents: list[Document],
    *,
    enqueue_task_fn: QueueEnqueuer,
) -> ResponseDict:
    task_type = "embeddings_vision" if settings.enable_vision_ocr else "embeddings_paperless"
    for doc in documents:
        enqueue_task_fn(settings, {"doc_id": doc.id, "task": task_type})
    state = get_or_create_state(db, "embeddings")
    state.status = "running"
    ensure_started(state)
    state.last_synced_at = datetime.now(UTC).isoformat()
    db.commit()
    return {"ingested": 0, "documents_embedded": 0, "queued": len(documents)}


def build_queue_status_response(
    settings: Settings,
    db: Session,
    state: SyncState | None,
    *,
    queue_stats_fn: QueueStatsFn,
) -> ResponseDict:
    stats = queue_stats_fn(settings) or {"length": 0, "total": 0, "in_progress": 0, "done": 0}
    status = "running" if (stats["length"] > 0 or stats["in_progress"] > 0) else "idle"
    if status == "running" and state and not state.started_at:
        state.started_at = datetime.now(UTC).isoformat()
        state.status = "running"
        db.commit()
    started_at = state.started_at if state else None
    eta_seconds = estimate_eta_seconds(started_at, stats["done"], stats["total"])
    return {
        "status": status,
        "processed": stats["done"],
        "total": stats["total"],
        "started_at": started_at,
        "last_synced_at": state.last_synced_at if state else None,
        "cancel_requested": state.cancel_requested if state else False,
        "eta_seconds": eta_seconds,
    }


def ingest_embeddings_for_documents(
    *,
    db: Session,
    settings: Settings,
    documents: list[Document],
    force: bool,
    ensure_embedding_collection_fn: EnsureEmbeddingCollectionFn,
    collect_page_texts_fn: CollectPageTextsFn,
    chunk_document_with_pages_fn: ChunkDocumentFn,
    delete_points_for_doc_fn: DeletePointsFn,
    embed_text_fn: EmbedTextFn,
    make_point_id_fn: MakePointIdFn,
    make_doc_point_id_fn: MakeDocPointIdFn,
    upsert_points_fn: UpsertPointsFn,
) -> ResponseDict:
    if not documents:
        state = get_or_create_state(db, "embeddings")
        state.status = "idle"
        state.last_synced_at = datetime.now(UTC).isoformat()
        db.commit()
        return {"ingested": 0, "documents_embedded": 0}

    ensure_embedding_collection_fn(settings)

    points_ingested = 0
    embedded = 0
    processed = 0
    state = get_or_create_state(db, "embeddings")
    mark_running(state, total=len(documents), processed=0)
    db.commit()
    logger.info("Embedding ingest started docs=%s force=%s", len(documents), force)
    for doc in documents:
        db.refresh(state)
        if state.cancel_requested:
            state.status = "cancelled"
            db.commit()
            return {"ingested": 0, "documents_embedded": embedded, "status": "cancelled"}
        content_value = doc.content or ""
        logger.info("Embedding doc=%s fetching page-aware text", doc.id)
        baseline_pages, vision_pages, page_texts = collect_page_texts_fn(
            settings,
            db,
            doc,
            force_vision=force,
        )
        if not content_value and not page_texts:
            processed += 1
            state.processed = processed
            continue
        hash_source = (
            "\f".join(f"{getattr(page, 'source', '')}:{getattr(page, 'text', '')}" for page in page_texts)
            if page_texts
            else content_value
        )
        content_hash = sha256((hash_source or "").encode("utf-8")).hexdigest()
        existing = db.get(DocumentEmbedding, doc.id)
        if (
            not force
            and existing
            and existing.content_hash == content_hash
            and existing.embedding_model == settings.embedding_model
            and existing.chunk_count
        ):
            logger.info("Skip embed doc=%s (unchanged)", doc.id)
            processed += 1
            state.processed = processed
            if processed % 5 == 0 or processed == state.total:
                db.commit()
            continue
        embedding_source = "vision" if vision_pages else "paperless"
        delete_points_for_doc_fn(settings, doc.id, embedding_source)
        baseline_chunks = chunk_document_with_pages_fn(settings, content_value, baseline_pages or None)
        vision_chunks = (
            chunk_document_with_pages_fn(settings, content_value, vision_pages or None)
            if vision_pages
            else []
        )
        chunks = baseline_chunks + vision_chunks
        logger.info("Embedding doc=%s chunks=%s page_texts=%s", doc.id, len(chunks), len(page_texts))
        doc_points: list[PointPayload] = []
        vectors: list[list[float]] = []
        for idx, chunk in enumerate(chunks):
            chunk_text_value = str(chunk["text"])
            vector = embed_text_fn(settings, chunk_text_value)
            vectors.append(vector)
            doc_points.append(
                {
                    "id": make_point_id_fn(doc.id, idx, embedding_source),
                    "vector": vector,
                    "payload": {
                        "doc_id": doc.id,
                        "chunk": idx,
                        "text": chunk_text_value,
                        "page": chunk.get("page"),
                        "source": chunk.get("source"),
                        "quality_score": chunk.get("quality_score"),
                        "bbox": chunk.get("bbox"),
                    },
                }
            )
            if idx % 5 == 0 or idx == len(chunks) - 1:
                logger.info("Embedding doc=%s chunk=%s/%s", doc.id, idx + 1, len(chunks))
        if vectors:
            doc_vector = average_vectors(vectors)
            if doc_vector:
                doc_points.append(
                    {
                        "id": make_doc_point_id_fn(doc.id),
                        "vector": doc_vector,
                        "payload": {
                            "doc_id": doc.id,
                            "chunk": -1,
                            "type": "doc",
                            "source": embedding_source,
                        },
                    }
                )
        if doc_points:
            logger.info("Upserting doc=%s points=%s", doc.id, len(doc_points))
            upsert_points_fn(settings, doc_points)
            points_ingested += len(doc_points)
        else:
            logger.info("Skipping doc=%s (no chunks)", doc.id)
        if not existing:
            existing = DocumentEmbedding(doc_id=doc.id)
            db.add(existing)
        existing.content_hash = content_hash
        existing.embedding_model = settings.embedding_model
        existing.embedded_at = datetime.now(UTC).isoformat()
        previous_source = str(existing.embedding_source or "").strip().lower()
        if previous_source == "both" or (previous_source and previous_source != embedding_source):
            existing.embedding_source = "both"
        else:
            existing.embedding_source = embedding_source
        existing.chunk_count = len(chunks)
        embedded += 1
        processed += 1
        state.processed = processed
        if processed % 5 == 0 or processed == state.total:
            logger.info("Embedding progress %s/%s", processed, state.total)
            db.commit()
    db.commit()
    state.status = "idle"
    state.last_synced_at = datetime.now(UTC).isoformat()
    db.commit()
    logger.info("Embedding ingest finished embedded=%s points=%s", embedded, points_ingested)
    return {"ingested": points_ingested, "documents_embedded": embedded}


def build_embedding_search_response(
    *,
    q: str,
    top_k: int,
    dedupe: bool,
    rerank: bool,
    source: str | None,
    min_quality: int | None,
    include_doc: bool,
    settings: Settings,
    db: Session,
    embed_text_fn: EmbedTextFn,
    search_points_fn: SearchPointsFn,
) -> ResponseDict:
    logger.info(
        "Search q=%s top_k=%s dedupe=%s rerank=%s source=%s include_doc=%s",
        q,
        top_k,
        dedupe,
        rerank,
        source,
        include_doc,
    )
    vector = embed_text_fn(settings, q)
    oversample = max(top_k * 6, top_k)
    raw = search_points_fn(
        settings,
        vector,
        limit=oversample,
        filter_payload={"must_not": [{"key": "type", "match": {"value": "doc"}}]},
    )
    raw_hits = raw.get("result", [])
    hits = raw_hits if isinstance(raw_hits, list) else []
    query_text = (q or "").strip().lower()
    query_tokens = [token for token in re.findall(r"[a-z0-9]+", query_text) if len(token) >= 2]
    query_token_set = set(query_tokens)
    results: list[dict[str, object]] = []
    for hit in hits:
        if not isinstance(hit, dict):
            continue
        payload = hit.get("payload")
        if not isinstance(payload, dict):
            continue
        if source and payload.get("source") != source:
            continue
        text = str(payload.get("text") or "")
        snippet = text[:240]
        quality_score = coerce_int(payload.get("quality_score"), default=100)
        if min_quality is not None and quality_score < min_quality:
            continue
        text_lower = text.lower()
        token_matches = sum(1 for token in query_token_set if token in text_lower)
        token_match_ratio = (token_matches / max(1, len(query_token_set))) if query_token_set else 0.0
        phrase_bonus = 0.5 if query_text and query_text in text_lower else 0.0
        base_score = coerce_float(hit.get("score")) * (float(quality_score) / 100.0)
        combined_score = base_score + (token_match_ratio * 0.35) + phrase_bonus
        results.append(
            {
                "doc_id": payload.get("doc_id"),
                "page": payload.get("page"),
                "snippet": snippet,
                "score": coerce_float(hit.get("score")),
                "source": payload.get("source"),
                "quality_score": quality_score,
                "bbox": payload.get("bbox"),
                "combined_score": combined_score,
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
                current_score = coerce_float(current.get("combined_score"))
                next_score = coerce_float(item.get("combined_score"))
                if next_score > current_score:
                    deduped[key] = item
            elif coerce_float(item.get("score")) > coerce_float(current.get("score")):
                deduped[key] = item
        matches = list(deduped.values())
    if rerank:
        matches.sort(key=lambda item: coerce_float(item.get("combined_score")), reverse=True)
    else:
        matches.sort(key=lambda item: coerce_float(item.get("score")), reverse=True)
    if top_k > 0:
        matches = matches[:top_k]
    if include_doc and matches:
        doc_ids = {item.get("doc_id") for item in matches if item.get("doc_id") is not None}
        normalized_doc_ids = [doc_id for doc_id in doc_ids if isinstance(doc_id, int)]
        if normalized_doc_ids:
            docs = db.query(Document).filter(Document.id.in_(normalized_doc_ids)).all()
            docs_by_id: dict[int, dict[str, object]] = {
                doc.id: {
                    "id": doc.id,
                    "title": doc.title,
                    "document_date": doc.document_date,
                    "created": doc.created,
                    "correspondent_id": doc.correspondent_id,
                }
                for doc in docs
            }
            corr_ids = [doc.correspondent_id for doc in docs if doc.correspondent_id]
            correspondents: dict[int, str | None] = {}
            if corr_ids:
                rows = db.query(Correspondent).filter(Correspondent.id.in_(corr_ids)).all()
                correspondents = {row.id: row.name for row in rows}
            for item in matches:
                doc_id = coerce_doc_id(item.get("doc_id"))
                doc = docs_by_id.get(doc_id) if doc_id is not None else None
                correspondent_id = coerce_doc_id(doc.get("correspondent_id")) if doc else None
                if doc and correspondent_id is not None:
                    doc["correspondent_name"] = correspondents.get(correspondent_id)
                item["document"] = doc
    logger.info("Search matches=%s", len(matches))
    return {"query": q, "top_k": top_k, "matches": matches}


def build_embedding_status_response(
    *,
    db: Session,
    settings: Settings,
    queue_stats_fn: QueueStatsFn,
) -> ResponseDict:
    state = db.get(SyncState, "embeddings")
    if settings.queue_enabled:
        return build_queue_status_response(settings, db, state, queue_stats_fn=queue_stats_fn)
    if not state:
        return {"status": "idle", "processed": 0, "total": 0, "started_at": None}
    eta_seconds = estimate_eta_seconds(state.started_at, state.processed, state.total)
    return {
        "status": state.status or "idle",
        "processed": state.processed or 0,
        "total": state.total or 0,
        "started_at": state.started_at,
        "last_synced_at": state.last_synced_at,
        "cancel_requested": state.cancel_requested or False,
        "eta_seconds": eta_seconds,
    }


def cancel_embeddings_ingest(db: Session) -> ResponseDict:
    state = db.get(SyncState, "embeddings")
    if not state:
        return {"status": "idle"}
    state.cancel_requested = True
    db.commit()
    return {"status": "cancelling"}


def average_vectors(vectors: list[list[float]]) -> list[float]:
    if not vectors:
        return []
    width = len(vectors[0])
    sums = [0.0] * width
    for vector in vectors:
        for idx, value in enumerate(vector):
            sums[idx] += value
    return [value / len(vectors) for value in sums]
