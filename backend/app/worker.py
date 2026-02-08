from __future__ import annotations

import logging
import os
import socket
import threading
import time

from sqlalchemy.orm import Session

from app.config import load_settings
from app.db import SessionLocal
from app.models import Document, DocumentEmbedding, DocumentPageText, SyncState
from app.services import paperless
from app.services.documents import fetch_pdf_bytes_for_doc, get_document_or_none
from app.services.embeddings import (
    chunk_document_with_pages,
    delete_points_for_doc,
    embed_text,
    make_point_id,
    upsert_points,
)
from app.services.embedding_init import ensure_embedding_collection
from app.services.queue import (
    QUEUE_KEY,
    _get_client,
    mark_in_progress,
    mark_done,
    QUEUE_SET,
    task_key,
    mark_worker_heartbeat,
    record_last_run,
    acquire_worker_lock,
    refresh_worker_lock,
    release_worker_lock,
    is_cancel_requested,
    clear_cancel,
    reset_stats,
    clear_queue,
    is_paused,
)
from app.services.text_pages import get_baseline_page_texts
from app.services.page_texts_merge import collect_page_texts
from app.services.page_text_store import upsert_page_texts
from app.services.ocr_scoring import ensure_document_ocr_score
from app.services.suggestions import generate_field_variants, generate_normalized_suggestions
from app.services.suggestion_store import audit_suggestion_run, persist_suggestions, upsert_suggestion
from app.services.meta_cache import get_cached_correspondents, get_cached_tags
from app.routes.sync import _upsert_document
from app.schemas import DocumentIn
import json

logger = logging.getLogger(__name__)


def _embed_with_pages(settings, db: Session, doc: Document, baseline_pages, vision_pages, embedding_source: str) -> None:
    content_value = doc.content or ""
    page_texts = (baseline_pages or []) + (vision_pages or [])
    hash_source = "\f".join(f"{page.source}:{page.text}" for page in page_texts) if page_texts else content_value
    content_hash = __import__("hashlib").sha256((hash_source or "").encode("utf-8")).hexdigest()

    ensure_embedding_collection(settings)
    delete_points_for_doc(settings, doc.id)
    baseline_chunks = chunk_document_with_pages(settings, content_value, baseline_pages or None)
    vision_chunks = (
        chunk_document_with_pages(settings, content_value, vision_pages or None) if vision_pages else []
    )
    chunks = baseline_chunks + vision_chunks
    points = []
    for idx, chunk in enumerate(chunks):
        chunk_text_value = str(chunk["text"])
        vector = embed_text(settings, chunk_text_value)
        points.append(
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
                    "bbox": chunk.get("bbox"),
                },
            }
        )
    if points:
        upsert_points(settings, points)

    existing = db.get(DocumentEmbedding, doc.id)
    if not existing:
        existing = DocumentEmbedding(doc_id=doc.id)
        db.add(existing)
    existing.content_hash = content_hash
    existing.embedding_model = settings.embedding_model
    existing.embedded_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
    existing.embedding_source = embedding_source
    existing.chunk_count = len(chunks)
    db.commit()


def _process_sync_only(settings, db: Session, doc_id: int) -> None:
    if is_cancel_requested(settings):
        logger.info("Worker cancel requested; abort sync doc=%s", doc_id)
        return
    raw = paperless.get_document(settings, doc_id)
    data = DocumentIn.model_validate(raw)
    cache = {"correspondents": set(), "document_types": set(), "tags": set()}
    _upsert_document(db, settings, data, cache)
    db.commit()
    doc = get_document_or_none(db, doc_id)
    if doc:
        ensure_document_ocr_score(settings, db, doc, "paperless_ocr")


def _process_doc(settings, db: Session, doc_id: int) -> None:
    if is_cancel_requested(settings):
        logger.info("Worker cancel requested; abort doc=%s", doc_id)
        return
    raw = paperless.get_document(settings, doc_id)
    data = DocumentIn.model_validate(raw)
    cache = {"correspondents": set(), "document_types": set(), "tags": set()}
    _upsert_document(db, settings, data, cache)
    db.commit()

    doc = get_document_or_none(db, doc_id)
    if not doc:
        return
    ensure_document_ocr_score(settings, db, doc, "paperless_ocr")

    # Embeddings (with vision OCR)
    baseline_pages, vision_pages, _ = collect_page_texts(
        settings,
        db,
        doc,
        force_vision=True,
    )
    if vision_pages:
        ensure_document_ocr_score(settings, db, doc, "vision_ocr")
    _embed_with_pages(settings, db, doc, baseline_pages, vision_pages)

    # Suggestions
    tags = get_cached_tags(settings)
    correspondents = get_cached_correspondents(settings)
    baseline_text = doc.content or ""
    baseline_suggestions = generate_normalized_suggestions(
        settings,
        raw,
        baseline_text,
        tags=tags,
        correspondents=correspondents,
    )
    persist_suggestions(
        db,
        doc_id,
        "paperless_ocr",
        baseline_suggestions,
        model_name=settings.text_model,
    )
    if vision_pages:
        vision_text = "\n\n".join(page.text or "" for page in vision_pages)
        vision_suggestions = generate_normalized_suggestions(
            settings,
            raw,
            vision_text,
            tags=tags,
            correspondents=correspondents,
        )
        persist_suggestions(
            db,
            doc_id,
            "vision_ocr",
            vision_suggestions,
            model_name=settings.text_model,
        )

def _process_vision_ocr_only(settings, db: Session, doc_id: int, force: bool = False) -> None:
    if is_cancel_requested(settings):
        logger.info("Worker cancel requested; abort vision OCR doc=%s", doc_id)
        return
    doc = get_document_or_none(db, doc_id)
    if not doc:
        return
    if not force:
        existing = (
            db.query(DocumentPageText)
            .filter(DocumentPageText.doc_id == doc_id, DocumentPageText.source == "vision_ocr")
            .first()
        )
        if existing:
            ensure_document_ocr_score(settings, db, doc, "vision_ocr")
            logger.info("Vision OCR skipped (cached) doc=%s", doc_id)
            return
    _, vision_pages, _ = collect_page_texts(
        settings,
        db,
        doc,
        force_vision=True,
    )
    if vision_pages:
        ensure_document_ocr_score(settings, db, doc, "vision_ocr", force=force)
    db.commit()

def _process_embeddings_paperless(settings, db: Session, doc_id: int) -> None:
    if is_cancel_requested(settings):
        logger.info("Worker cancel requested; abort embeddings doc=%s", doc_id)
        return
    doc = get_document_or_none(db, doc_id)
    if not doc:
        return
    baseline_pages = get_baseline_page_texts(
        settings,
        doc.content,
        fetch_pdf_bytes=lambda: fetch_pdf_bytes_for_doc(settings, doc),
    )
    _embed_with_pages(settings, db, doc, baseline_pages, [], "paperless")


def _process_embeddings_vision(settings, db: Session, doc_id: int) -> None:
    if is_cancel_requested(settings):
        logger.info("Worker cancel requested; abort embeddings doc=%s", doc_id)
        return
    doc = get_document_or_none(db, doc_id)
    if not doc:
        return
    baseline_pages, vision_pages, _ = collect_page_texts(
        settings,
        db,
        doc,
        force_vision=False,
    )
    _embed_with_pages(settings, db, doc, baseline_pages, vision_pages, "vision")


def _process_suggestions_paperless(settings, db: Session, doc_id: int) -> None:
    if is_cancel_requested(settings):
        logger.info("Worker cancel requested; abort suggestions doc=%s", doc_id)
        return
    doc = get_document_or_none(db, doc_id)
    if not doc:
        return
    tags = get_cached_tags(settings)
    correspondents = get_cached_correspondents(settings)
    raw = paperless.get_document(settings, doc_id)
    baseline_text = doc.content or ""
    baseline_suggestions = generate_normalized_suggestions(
        settings,
        raw,
        baseline_text,
        tags=tags,
        correspondents=correspondents,
    )
    persist_suggestions(
        db,
        doc_id,
        "paperless_ocr",
        baseline_suggestions,
        model_name=settings.text_model,
    )


def _process_suggestions_vision(settings, db: Session, doc_id: int) -> None:
    if is_cancel_requested(settings):
        logger.info("Worker cancel requested; abort vision suggestions doc=%s", doc_id)
        return
    tags = get_cached_tags(settings)
    correspondents = get_cached_correspondents(settings)
    raw = paperless.get_document(settings, doc_id)
    vision_pages = (
        db.query(DocumentPageText)
        .filter(DocumentPageText.doc_id == doc_id, DocumentPageText.source == "vision_ocr")
        .order_by(DocumentPageText.page.asc())
        .all()
    )
    if vision_pages:
        vision_text = "\n\n".join(page.text or "" for page in vision_pages).strip()
        if vision_text:
            vision_suggestions = generate_normalized_suggestions(
                settings,
                raw,
                vision_text,
                tags=tags,
                correspondents=correspondents,
            )
            persist_suggestions(
                db,
                doc_id,
                "vision_ocr",
                vision_suggestions,
                model_name=settings.text_model,
            )


def _process_suggest_field(settings, db: Session, task: dict) -> None:
    doc_id = int(task.get("doc_id"))
    source = str(task.get("source") or "paperless_ocr")
    field = str(task.get("field") or "")
    count = int(task.get("count") or 3)
    current = task.get("current")
    if source not in ("paperless_ocr", "vision_ocr") or field not in ("title", "date", "correspondent", "tags"):
        return
    raw = paperless.get_document(settings, doc_id)
    tags = get_cached_tags(settings)
    correspondents = get_cached_correspondents(settings)
    if source == "vision_ocr":
        vision_pages = (
            db.query(DocumentPageText)
            .filter(DocumentPageText.doc_id == doc_id, DocumentPageText.source == "vision_ocr")
            .order_by(DocumentPageText.page.asc())
            .all()
        )
        text = "\n\n".join(page.text or "" for page in vision_pages)
    else:
        doc = get_document_or_none(db, doc_id)
        text = doc.content if doc else ""
    variants = generate_field_variants(
        settings,
        raw,
        text or "",
        tags=tags,
        correspondents=correspondents,
        field=field,
        count=max(1, min(count, 5)),
        current_value=current,
    )
    variant_source = ("pvar" if source == "paperless_ocr" else "vvar") + f":{field}"
    upsert_suggestion(
        db,
        doc_id,
        variant_source,
        json.dumps(
            {"variants": variants.get("variants") if isinstance(variants, dict) else variants},
            ensure_ascii=False,
        ),
        model_name=settings.text_model,
        commit=False,
    )
    audit_suggestion_run(db, doc_id, source, f"field_variants:{field}", commit=False)
    db.commit()


def _dispatch_task(settings, db: Session, task_type: str, doc_id: int, task: dict | None) -> None:
    handlers = {
        "sync": lambda: _process_sync_only(settings, db, doc_id),
        "embeddings_paperless": lambda: _process_embeddings_paperless(settings, db, doc_id),
        "embeddings_vision": lambda: _process_embeddings_vision(settings, db, doc_id),
        "suggestions_paperless": lambda: _process_suggestions_paperless(settings, db, doc_id),
        "suggestions_vision": lambda: _process_suggestions_vision(settings, db, doc_id),
        "suggest_field": lambda: _process_suggest_field(settings, db, task or {}),
    }
    if task_type == "vision_ocr":
        force = bool(task.get("force")) if isinstance(task, dict) else False
        _process_vision_ocr_only(settings, db, doc_id, force=force)
        return
    handler = handlers.get(task_type)
    if handler:
        handler()
        return
    _process_doc(settings, db, doc_id)


def main() -> None:
    settings = load_settings()
    if not settings.queue_enabled:
        raise SystemExit("QUEUE_ENABLED is not set")
    client = _get_client(settings)
    if not client:
        raise SystemExit("Redis not configured")
    worker_token = f"{socket.gethostname()}:{os.getpid()}:{int(time.time())}"
    while not acquire_worker_lock(settings, worker_token):
        logger.warning("Worker lock unavailable or Redis not ready; retrying in 5s")
        time.sleep(5)
    logger.info("Worker started queue=%s", QUEUE_KEY)
    stop_event = threading.Event()
    lock_lost = threading.Event()

    def _lock_refresher() -> None:
        while not stop_event.is_set():
            if not refresh_worker_lock(settings, worker_token):
                logger.error("Worker lock refresh failed; exiting soon")
                lock_lost.set()
                return
            stop_event.wait(30)

    refresher = threading.Thread(target=_lock_refresher, name="worker-lock-refresher", daemon=True)
    refresher.start()
    try:
        while True:
            if lock_lost.is_set():
                raise SystemExit("Worker lock lost; exiting")
            mark_worker_heartbeat(settings)
            if is_paused(settings):
                time.sleep(0.5)
                continue
            if is_cancel_requested(settings):
                logger.info("Worker cancel requested; clearing queue")
                clear_queue(settings)
                reset_stats(settings)
                clear_cancel(settings)
                time.sleep(0.5)
                continue
            item = client.blpop(QUEUE_KEY, timeout=5)
            if not item:
                time.sleep(0.5)
                continue
            _, doc_id_str = item
            task = None
            try:
                task = json.loads(doc_id_str)
            except Exception:
                task = None
            if isinstance(task, dict) and "doc_id" in task:
                doc_id = int(task.get("doc_id"))
                task_type = str(task.get("task") or "full")
            else:
                try:
                    doc_id = int(doc_id_str)
                except Exception:
                    logger.warning("Invalid doc_id in queue: %s", doc_id_str)
                    continue
                task_type = "full"
            if is_cancel_requested(settings):
                logger.info("Worker cancel requested; skipping doc=%s", doc_id)
                clear_queue(settings)
                reset_stats(settings)
                clear_cancel(settings)
                time.sleep(0.5)
                continue
            mark_in_progress(settings)
            run_started = time.time()
            try:
                with SessionLocal() as db:
                    _dispatch_task(settings, db, task_type, doc_id, task if isinstance(task, dict) else None)
            except Exception as exc:
                logger.exception("Worker failed doc=%s error=%s", doc_id, exc)
            finally:
                mark_done(settings)
                record_last_run(settings, time.time() - run_started)
                if client:
                    if isinstance(task, dict):
                        client.srem(QUEUE_SET, task_key(task))
                    else:
                        client.srem(QUEUE_SET, str(doc_id))
    finally:
        stop_event.set()
        release_worker_lock(settings, worker_token)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    main()
