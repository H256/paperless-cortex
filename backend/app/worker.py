from __future__ import annotations

import logging
import time

from sqlalchemy.orm import Session

from app.config import load_settings
from app.db import SessionLocal
from app.models import Document, DocumentEmbedding, SyncState
from app.services import paperless
from app.services.embeddings import (
    chunk_document_with_pages,
    delete_points_for_doc,
    embed_text,
    ensure_qdrant_collection,
    make_point_id,
    upsert_points,
)
from app.services.queue import (
    QUEUE_KEY,
    _get_client,
    mark_in_progress,
    mark_done,
    QUEUE_SET,
    mark_worker_heartbeat,
)
from app.services.text_pages import get_page_text_layers
from app.services.page_text_store import upsert_page_texts
from app.services.suggestions import generate_suggestions, normalize_suggestions_payload
from app.services.suggestion_store import upsert_suggestion, audit_suggestion_run
from app.services.meta_cache import get_cached_correspondents, get_cached_tags
from app.routes.sync import _upsert_document
from app.schemas import DocumentIn

logger = logging.getLogger(__name__)


def _process_doc(settings, db: Session, doc_id: int) -> None:
    raw = paperless.get_document(settings, doc_id)
    data = DocumentIn.model_validate(raw)
    cache = {"correspondents": set(), "document_types": set(), "tags": set()}
    _upsert_document(db, settings, data, cache)
    db.commit()

    doc = db.get(Document, doc_id)
    if not doc:
        return

    # Embeddings (with vision OCR)
    content_value = doc.content or ""
    baseline_pages, vision_pages = get_page_text_layers(
        settings,
        doc.content,
        fetch_pdf_bytes=lambda: paperless.get_document_pdf(settings, doc.id),
        force_full_vision=True,
    )
    if vision_pages:
        upsert_page_texts(db, settings, doc.id, vision_pages, source_filter="vision_ocr")
    page_texts = baseline_pages + vision_pages
    hash_source = "\f".join(f"{page.source}:{page.text}" for page in page_texts) if page_texts else content_value
    content_hash = __import__("hashlib").sha256((hash_source or "").encode("utf-8")).hexdigest()

    sample_embedding = embed_text(settings, "dimension probe")
    ensure_qdrant_collection(settings, vector_size=len(sample_embedding))
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
    existing.chunk_count = len(chunks)
    db.commit()

    # Suggestions
    tags = get_cached_tags(settings)
    correspondents = get_cached_correspondents(settings)
    baseline_suggestions = generate_suggestions(settings, raw, content_value, tags, correspondents)
    baseline_suggestions = normalize_suggestions_payload(baseline_suggestions, tags)
    upsert_suggestion(db, doc_id, "paperless_ocr", __import__("json").dumps(baseline_suggestions, ensure_ascii=False))
    audit_suggestion_run(db, doc_id, "paperless_ocr", "suggestions_generate")
    if vision_pages:
        vision_text = "\n\n".join(page.text or "" for page in vision_pages)
        vision_suggestions = generate_suggestions(settings, raw, vision_text, tags, correspondents)
        vision_suggestions = normalize_suggestions_payload(vision_suggestions, tags)
        upsert_suggestion(db, doc_id, "vision_ocr", __import__("json").dumps(vision_suggestions, ensure_ascii=False))
        audit_suggestion_run(db, doc_id, "vision_ocr", "suggestions_generate")


def main() -> None:
    settings = load_settings()
    if not settings.queue_enabled:
        raise SystemExit("QUEUE_ENABLED is not set")
    client = _get_client(settings)
    if not client:
        raise SystemExit("Redis not configured")
    logger.info("Worker started queue=%s", QUEUE_KEY)
    while True:
        mark_worker_heartbeat(settings)
        item = client.blpop(QUEUE_KEY, timeout=5)
        if not item:
            time.sleep(0.5)
            continue
        _, doc_id_str = item
        try:
            doc_id = int(doc_id_str)
        except Exception:
            logger.warning("Invalid doc_id in queue: %s", doc_id_str)
            continue
        mark_in_progress(settings)
        try:
            with SessionLocal() as db:
                _process_doc(settings, db, doc_id)
        except Exception as exc:
            logger.exception("Worker failed doc=%s error=%s", doc_id, exc)
        finally:
            mark_done(settings)
            if client:
                client.srem(QUEUE_SET, str(doc_id))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    main()
