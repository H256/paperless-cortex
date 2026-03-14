from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

from app.api_models import DocumentIn
from app.models import Document, DocumentEmbedding
from app.services.ai.ocr_scoring import ensure_document_ocr_score
from app.services.documents.documents import fetch_pdf_bytes_for_doc, get_document_or_none
from app.services.documents.page_texts_merge import collect_page_texts
from app.services.documents.page_types import PageText
from app.services.documents.sync_operations import upsert_document
from app.services.documents.text_cleaning import clean_ocr_text
from app.services.documents.text_pages import get_baseline_page_texts
from app.services.integrations import paperless
from app.services.pipeline.worker_checkpoint import (
    get_task_run_checkpoint,
    resume_stage_current,
    set_task_checkpoint,
)
from app.services.search.embedding_init import ensure_embedding_collection
from app.services.search.embeddings import (
    average_vectors,
    chunk_document_with_pages,
    delete_points_for_doc,
    embed_texts,
    enforce_embedding_chunk_budget,
    make_doc_point_id,
    make_point_id,
    rebuild_doc_point_from_chunks,
    summarize_chunk_split_telemetry,
    upsert_points,
)
from app.services.search.evidence_index import extract_pdf_page_anchors, upsert_page_anchors

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from typing import Protocol

    from sqlalchemy.orm import Session

    from app.config import Settings
    from app.services.documents.page_types import WordBox

    class SupportsEmbeddingPage(Protocol):
        page: int
        source: str

logger = logging.getLogger(__name__)


def _page_text_value(page: object) -> str:
    clean_text = getattr(page, "clean_text", None)
    if isinstance(clean_text, str) and clean_text.strip():
        return clean_text
    raw_text = getattr(page, "text", None)
    if isinstance(raw_text, str):
        return clean_ocr_text(raw_text)
    return ""


def _page_quality_score(page: object) -> int | None:
    score = getattr(page, "quality_score", None)
    return score if isinstance(score, int) else None


def _page_words(page: object) -> list[WordBox] | None:
    words = getattr(page, "words", None)
    return words if isinstance(words, list) else None


def _embedding_checkpoint_batch_size(
    *,
    total_chunks: int,
    configured_batch_size: int,
) -> int:
    if total_chunks >= 1200:
        return min(configured_batch_size, 4)
    if total_chunks >= 600:
        return min(configured_batch_size, 6)
    if total_chunks >= 250:
        return min(configured_batch_size, 8)
    return configured_batch_size


def embed_with_pages(
    settings: Settings,
    db: Session,
    doc: Document,
    baseline_pages: Sequence[SupportsEmbeddingPage] | None,
    vision_pages: Sequence[SupportsEmbeddingPage] | None,
    embedding_source: str,
    *,
    run_id: int | None = None,
) -> None:
    content_value = clean_ocr_text(doc.content or "")
    baseline_page_list = list(baseline_pages or [])
    vision_page_list = list(vision_pages or [])
    page_texts = baseline_page_list + vision_page_list
    hash_source = (
        "\f".join(f"{page.source}:{_page_text_value(page)}" for page in page_texts)
        if page_texts
        else content_value
    )
    content_hash = hashlib.sha256((hash_source or "").encode("utf-8")).hexdigest()

    ensure_embedding_collection(settings)
    normalized_baseline_pages = [
        PageText(
            page=page.page,
            text=_page_text_value(page),
            source=page.source,
            quality_score=_page_quality_score(page),
            words=_page_words(page),
        )
        for page in baseline_page_list
    ]
    normalized_vision_pages = [
        PageText(
            page=page.page,
            text=_page_text_value(page),
            source=page.source,
            quality_score=_page_quality_score(page),
            words=_page_words(page),
        )
        for page in vision_page_list
    ]
    baseline_chunks = chunk_document_with_pages(settings, content_value, normalized_baseline_pages or None)
    vision_chunks = (
        chunk_document_with_pages(settings, content_value, normalized_vision_pages or None)
        if normalized_vision_pages
        else []
    )
    chunks = enforce_embedding_chunk_budget(settings, baseline_chunks + vision_chunks)
    telemetry: dict[str, int] = summarize_chunk_split_telemetry(chunks)
    max_chunks = max(0, int(settings.embedding_max_chunks_per_doc))
    if max_chunks > 0 and len(chunks) > max_chunks:
        logger.warning(
            "Embedding chunks capped doc=%s chunks=%s cap=%s",
            doc.id,
            len(chunks),
            max_chunks,
        )
        chunks = chunks[:max_chunks]

    configured_batch_size = max(1, int(settings.embedding_batch_size))
    batch_size = _embedding_checkpoint_batch_size(
        total_chunks=len(chunks),
        configured_batch_size=configured_batch_size,
    )
    checkpoint = get_task_run_checkpoint(db, run_id=run_id)
    resume_current = resume_stage_current(
        checkpoint,
        stage="embedding_chunks",
        source=embedding_source,
        total=len(chunks),
    )
    start_index = max(0, min(resume_current, len(chunks)))
    if start_index <= 0:
        delete_points_for_doc(settings, doc.id, source=embedding_source)
    else:
        logger.info(
            "Embedding resume doc=%s source=%s start_chunk=%s total=%s",
            doc.id,
            embedding_source,
            start_index,
            len(chunks),
        )

    set_task_checkpoint(
        db,
        run_id=run_id,
        stage="embedding_chunks",
        current=start_index,
        total=len(chunks),
        extra={
            "source": embedding_source,
            "batch_size": batch_size,
            "resumed": start_index > 0,
            **telemetry,
        },
    )
    doc_vectors: list[list[float]] = []
    for start in range(start_index, len(chunks), batch_size):
        chunk_batch = chunks[start : start + batch_size]
        texts = [str(chunk["text"]) for chunk in chunk_batch]
        vectors = embed_texts(settings, texts, telemetry=telemetry)
        doc_vectors.extend(vectors)
        points = []
        for offset, (chunk, vector) in enumerate(zip(chunk_batch, vectors, strict=False)):
            chunk_idx = start + offset
            chunk_text_value = texts[offset]
            points.append(
                {
                    "id": make_point_id(doc.id, chunk_idx, embedding_source),
                    "vector": vector,
                    "payload": {
                        "doc_id": doc.id,
                        "chunk": chunk_idx,
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
        logger.info(
            "Embedding progress doc=%s chunks=%s/%s",
            doc.id,
            min(start + len(chunk_batch), len(chunks)),
            len(chunks),
        )
        set_task_checkpoint(
            db,
            run_id=run_id,
            stage="embedding_chunks",
            current=min(start + len(chunk_batch), len(chunks)),
            total=len(chunks),
            extra={"source": embedding_source, "batch_size": batch_size, **telemetry},
        )

    if start_index > 0:
        rebuild_doc_point_from_chunks(
            settings,
            doc_id=int(doc.id),
            chunk_count=len(chunks),
            source_hint=embedding_source,
        )
    elif doc_vectors:
        doc_vector = average_vectors(doc_vectors)
        if doc_vector:
            upsert_points(
                settings,
                [
                    {
                        "id": make_doc_point_id(doc.id),
                        "vector": doc_vector,
                        "payload": {
                            "doc_id": doc.id,
                            "chunk": -1,
                            "type": "doc",
                            "source": embedding_source,
                        },
                    }
                ],
            )

    existing = db.get(DocumentEmbedding, doc.id)
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
    db.commit()


def process_sync_only(
    settings: Settings,
    db: Session,
    doc_id: int,
    *,
    is_cancel_requested_fn: Callable[[Settings], bool],
) -> None:
    if is_cancel_requested_fn(settings):
        logger.info("Worker cancel requested; abort sync doc=%s", doc_id)
        return
    raw = paperless.get_document(settings, doc_id)
    data = DocumentIn.model_validate(raw)
    cache: dict[str, set[int]] = {"correspondents": set(), "document_types": set(), "tags": set()}
    upsert_document(db, settings, data, cache)
    db.commit()
    doc = get_document_or_none(db, doc_id)
    if doc:
        ensure_document_ocr_score(settings, db, doc, "paperless_ocr")


def process_embeddings_paperless(
    settings: Settings,
    db: Session,
    doc_id: int,
    *,
    is_cancel_requested_fn: Callable[[Settings], bool],
    run_id: int | None = None,
) -> None:
    if is_cancel_requested_fn(settings):
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
    embed_with_pages(
        settings,
        db,
        doc,
        cast("Sequence[SupportsEmbeddingPage]", baseline_pages),
        [],
        "paperless",
        run_id=run_id,
    )


def process_evidence_index(
    settings: Settings,
    db: Session,
    doc_id: int,
    *,
    source: str = "paperless_pdf",
    is_cancel_requested_fn: Callable[[Settings], bool],
    run_id: int | None = None,
) -> None:
    if is_cancel_requested_fn(settings):
        logger.info("Worker cancel requested; abort evidence index doc=%s", doc_id)
        return
    if source != "paperless_pdf":
        logger.info("Evidence index source unsupported doc=%s source=%s", doc_id, source)
        return
    doc = get_document_or_none(db, doc_id)
    if not doc:
        return
    pdf_bytes = fetch_pdf_bytes_for_doc(settings, doc)
    rows = extract_pdf_page_anchors(pdf_bytes)
    set_task_checkpoint(
        db,
        run_id=run_id,
        stage="evidence_index",
        current=len(rows),
        total=len(rows),
        extra={"source": source},
    )
    upsert_page_anchors(db, doc_id=doc_id, source=source, rows=rows)


def process_embeddings_vision(
    settings: Settings,
    db: Session,
    doc_id: int,
    *,
    is_cancel_requested_fn: Callable[[Settings], bool],
    run_id: int | None = None,
) -> None:
    if is_cancel_requested_fn(settings):
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
    embed_with_pages(
        settings,
        db,
        doc,
        cast("Sequence[SupportsEmbeddingPage]", baseline_pages),
        cast("Sequence[SupportsEmbeddingPage]", vision_pages),
        "vision",
        run_id=run_id,
    )


def process_similarity_index(
    settings: Settings,
    db: Session,
    doc_id: int,
    *,
    is_cancel_requested_fn: Callable[[Settings], bool],
) -> None:
    if is_cancel_requested_fn(settings):
        logger.info("Worker cancel requested; abort similarity index doc=%s", doc_id)
        return
    embedding = db.get(DocumentEmbedding, int(doc_id))
    if not embedding or int(embedding.chunk_count or 0) <= 0:
        return
    ok = rebuild_doc_point_from_chunks(
        settings,
        doc_id=int(doc_id),
        chunk_count=int(embedding.chunk_count or 0),
        source_hint=str(embedding.embedding_source or ""),
    )
    if not ok:
        raise RuntimeError(
            f"similarity_index_rebuild_failed doc_id={int(doc_id)} "
            f"chunk_count={int(embedding.chunk_count or 0)} source={embedding.embedding_source or ''!s} "
            f"provider={settings.vector_store_provider} chunk vectors missing in active vector store"
        )
