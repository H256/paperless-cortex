from __future__ import annotations

import hashlib
import logging
import os
import socket
import threading
import time
from datetime import datetime, timezone
from collections.abc import Iterable

from sqlalchemy.orm import Session

from app.config import load_settings
from app.db import SessionLocal
from app.models import (
    Document,
    DocumentEmbedding,
    DocumentPageNote,
    DocumentPageText,
    DocumentSectionSummary,
    DocumentSuggestion,
    SyncState,
    TaskRun,
)
from app.services import paperless
from app.services.documents import fetch_pdf_bytes_for_doc, get_document_or_none
from app.services.embeddings import (
    chunk_document_with_pages,
    enforce_embedding_chunk_budget,
    summarize_chunk_split_telemetry,
    delete_points_for_doc,
    embed_texts,
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
    set_running_task,
    clear_running_task,
    enqueue_task,
    enqueue_task_delayed,
    move_due_delayed_tasks,
    add_dead_letter,
)
from app.services.text_pages import get_baseline_page_texts
from app.services.page_texts_merge import collect_page_texts
from app.services.page_text_store import upsert_page_texts
from app.services.page_text_store import reclean_page_texts
from app.services.page_types import PageText
from app.services.ocr_scoring import ensure_document_ocr_score
from app.services.suggestions import generate_field_variants, generate_normalized_suggestions
from app.services.suggestion_store import audit_suggestion_run, persist_suggestions, upsert_suggestion
from app.services.meta_cache import get_cached_correspondents, get_cached_tags
from app.services import vision_ocr
from app.services.text_cleaning import clean_ocr_text
from app.services.evidence_index import extract_pdf_page_anchors, upsert_page_anchors
from app.services.error_types import classify_worker_error
from app.services.error_types import is_retryable_error_type
from app.services.error_types import task_source_from_payload
from app.services.logging_setup import configure_logging, log_event
from app.services.hierarchical_summary import (
    generate_global_summary,
    generate_page_notes,
    generate_section_summary,
    group_notes_into_sections,
    is_large_document,
    replace_section_summaries,
    upsert_page_note,
)
from app.routes.sync import _upsert_document
from app.schemas import DocumentIn
from app.services.task_runs import (
    create_task_run,
    find_latest_checkpoint,
    finish_task_run,
    update_task_run_checkpoint,
)
import json

logger = logging.getLogger(__name__)
HEARTBEAT_INTERVAL_SECONDS = 5
VISION_OCR_BATCH_DEFAULT = 25


def _safe_rollback(db: Session, *, context: str = "") -> None:
    try:
        db.rollback()
    except Exception:
        if context:
            logger.debug("DB rollback failed context=%s", context, exc_info=True)


def _page_text_value(page: object) -> str:
    clean_text = getattr(page, "clean_text", None)
    if isinstance(clean_text, str) and clean_text.strip():
        return clean_text
    raw_text = getattr(page, "text", None)
    if isinstance(raw_text, str):
        return clean_ocr_text(raw_text)
    return ""


def _set_task_checkpoint(
    db: Session,
    *,
    run_id: int | None,
    stage: str,
    current: int | None = None,
    total: int | None = None,
    extra: dict | None = None,
) -> None:
    if run_id is None:
        return
    payload = {"stage": stage}
    if current is not None:
        payload["current"] = int(current)
    if total is not None:
        payload["total"] = int(total)
    if extra:
        payload.update(extra)
    try:
        update_task_run_checkpoint(db, run_id=run_id, checkpoint=payload)
    except Exception:
        logger.warning("Failed to persist task checkpoint run_id=%s stage=%s", run_id, stage)


def _get_task_run_checkpoint(db: Session, *, run_id: int | None) -> dict | None:
    if run_id is None:
        return None
    try:
        row = db.get(TaskRun, run_id)
    except Exception:
        # Worker must stay operational even when task-runs schema is not ready yet.
        logger.debug("Failed reading task run checkpoint run_id=%s", run_id, exc_info=True)
        return None
    if not row or not row.checkpoint_json:
        return None
    raw = str(row.checkpoint_json).strip()
    if not raw.startswith(("{", "[")):
        return None
    try:
        payload = json.loads(raw)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _resume_stage_current(
    checkpoint: dict | None,
    *,
    stage: str,
    source: str | None = None,
    total: int | None = None,
) -> int:
    if not checkpoint:
        return 0
    candidate = checkpoint
    resume_from = checkpoint.get("resume_from")
    if isinstance(resume_from, dict):
        candidate = resume_from
    if str(candidate.get("stage") or "").strip() != stage:
        return 0
    candidate_source = str(candidate.get("source") or "").strip()
    if source and candidate_source and candidate_source != source:
        return 0
    if total is not None:
        candidate_total = candidate.get("total")
        if isinstance(candidate_total, int) and candidate_total > 0 and candidate_total != total:
            return 0
    try:
        current = int(candidate.get("current") or 0)
    except Exception:
        return 0
    if total is not None:
        return max(0, min(current, int(total)))
    return max(0, current)


def _vision_ocr_batch_size(
    *,
    total_pages: int,
    configured_batch_size: int,
) -> int:
    # Large runs checkpoint more frequently and reduce rework on retries.
    if total_pages >= 300:
        return min(configured_batch_size, 5)
    if total_pages >= 120:
        return min(configured_batch_size, 10)
    return configured_batch_size


def _embedding_checkpoint_batch_size(
    *,
    total_chunks: int,
    configured_batch_size: int,
) -> int:
    # Very large chunk sets use smaller batches to report progress more often.
    if total_chunks >= 1200:
        return min(configured_batch_size, 4)
    if total_chunks >= 600:
        return min(configured_batch_size, 6)
    if total_chunks >= 250:
        return min(configured_batch_size, 8)
    return configured_batch_size


def _join_page_texts_limited(pages: Iterable[object], max_chars: int) -> str:
    if max_chars <= 0:
        return "\n\n".join(_page_text_value(page) for page in pages).strip()
    parts: list[str] = []
    total = 0
    for page in pages:
        text = _page_text_value(page).strip()
        if not text:
            continue
        sep_len = 2 if parts else 0
        remaining = max_chars - total - sep_len
        if remaining <= 0:
            break
        if len(text) > remaining:
            parts.append(text[:remaining])
            total = max_chars
            break
        parts.append(text)
        total += sep_len + len(text)
    return "\n\n".join(parts).strip()


def _is_large_doc(settings, doc: Document) -> bool:
    return is_large_document(
        page_count=doc.page_count,
        total_text=doc.content,
        threshold_pages=settings.large_doc_page_threshold,
    )


def _ensure_paperless_page_texts(settings, db: Session, doc: Document) -> None:
    baseline_pages = get_baseline_page_texts(
        settings,
        doc.content,
        fetch_pdf_bytes=lambda: fetch_pdf_bytes_for_doc(settings, doc),
    )
    if baseline_pages:
        upsert_page_texts(
            db,
            settings,
            doc.id,
            baseline_pages,
            source_filter="paperless_ocr",
            replace_pages=[page.page for page in baseline_pages],
        )


def _build_distilled_context_from_page_notes(
    db: Session,
    *,
    doc_id: int,
    source: str,
    max_chars: int,
) -> str:
    if max_chars <= 0:
        max_chars = 12000
    rows = (
        db.query(DocumentPageNote)
        .filter(
            DocumentPageNote.doc_id == doc_id,
            DocumentPageNote.source == source,
            DocumentPageNote.status == "ok",
        )
        .order_by(DocumentPageNote.page.asc())
        .all()
    )
    if not rows:
        return ""
    parts: list[str] = []
    used = 0
    for row in rows:
        raw = (row.notes_text or "").strip()
        if not raw:
            continue
        text = raw
        try:
            payload_obj = json.loads(raw)
            if isinstance(payload_obj, dict):
                direct = str(payload_obj.get("text") or "").strip()
                if direct:
                    text = direct
                else:
                    parts_list: list[str] = []
                    for key in ("facts", "entities", "references", "key_numbers", "uncertainties"):
                        values = payload_obj.get(key)
                        if isinstance(values, list):
                            cleaned = [str(v).strip() for v in values if str(v).strip()]
                            if cleaned:
                                parts_list.append(f"{key}: " + "; ".join(cleaned[:12]))
                    text = "\n".join(parts_list).strip() or raw
        except Exception:
            text = raw
        if not text:
            continue
        block = f"Page {row.page}: {text}"
        sep = "\n\n" if parts else ""
        remaining = max_chars - used - len(sep)
        if remaining <= 0:
            break
        if len(block) > remaining:
            parts.append(block[:remaining])
            break
        parts.append(block)
        used += len(sep) + len(block)
    return "\n\n".join(parts).strip()


def _build_distilled_context_from_hier_summary(
    db: Session,
    *,
    doc_id: int,
    source: str,
    max_chars: int,
) -> str:
    if max_chars <= 0:
        max_chars = 12000
    row = (
        db.query(DocumentSuggestion)
        .filter(
            DocumentSuggestion.doc_id == doc_id,
            DocumentSuggestion.source == "hier_summary",
        )
        .first()
    )
    if not row or not row.payload:
        return ""
    try:
        payload = json.loads(row.payload)
    except Exception:
        return ""
    if not isinstance(payload, dict):
        return ""
    payload_source = str(payload.get("source") or "").strip()
    if payload_source and payload_source != source:
        return ""

    summary = str(payload.get("summary") or "").strip()
    executive = str(payload.get("executive_summary") or "").strip()
    key_facts = payload.get("key_facts") if isinstance(payload.get("key_facts"), list) else []
    key_entities = payload.get("key_entities") if isinstance(payload.get("key_entities"), list) else []
    key_numbers = payload.get("key_numbers") if isinstance(payload.get("key_numbers"), list) else []
    key_dates = payload.get("key_dates") if isinstance(payload.get("key_dates"), list) else []
    has_signal = bool(summary or executive or key_facts or key_entities or key_numbers or key_dates)
    if not has_signal:
        notes = payload.get("confidence_notes") if isinstance(payload.get("confidence_notes"), list) else []
        note_text = " ".join(str(item).strip() for item in notes if str(item).strip()).lower()
        if "global_summary_error" in note_text or "fallback_due_to_json_parse_error" in note_text:
            return ""

    blocks: list[str] = []
    if executive:
        blocks.append(f"Executive summary: {executive}")
    if summary:
        blocks.append(f"Summary: {summary}")

    key_mappings = (
        ("key_facts", "Key facts"),
        ("key_dates", "Key dates"),
        ("key_entities", "Key entities"),
        ("key_numbers", "Key numbers"),
        ("open_questions", "Open questions"),
        ("confidence_notes", "Confidence notes"),
    )
    for key, label in key_mappings:
        values = payload.get(key)
        if not isinstance(values, list):
            continue
        cleaned = [str(item).strip() for item in values if str(item).strip()]
        if not cleaned:
            continue
        blocks.append(f"{label}: " + "; ".join(cleaned[:20]))

    if not blocks:
        return ""

    parts: list[str] = []
    used = 0
    for block in blocks:
        sep = "\n\n" if parts else ""
        remaining = max_chars - used - len(sep)
        if remaining <= 0:
            break
        if len(block) > remaining:
            parts.append(block[:remaining])
            break
        parts.append(block)
        used += len(sep) + len(block)
    return "\n\n".join(parts).strip()


def _embed_with_pages(settings, db: Session, doc: Document, baseline_pages, vision_pages, embedding_source: str, run_id: int | None = None) -> None:
    content_value = clean_ocr_text(doc.content or "")
    page_texts = (baseline_pages or []) + (vision_pages or [])
    hash_source = (
        "\f".join(f"{page.source}:{_page_text_value(page)}" for page in page_texts)
        if page_texts
        else content_value
    )
    content_hash = hashlib.sha256((hash_source or "").encode("utf-8")).hexdigest()

    ensure_embedding_collection(settings)
    normalized_baseline_pages = []
    for page in baseline_pages or []:
        normalized_baseline_pages.append(
            PageText(
                page=page.page,
                text=_page_text_value(page),
                source=page.source,
                quality_score=getattr(page, "quality_score", None),
                words=getattr(page, "words", None),
            )
        )
    normalized_vision_pages = []
    for page in vision_pages or []:
        normalized_vision_pages.append(
            PageText(
                page=page.page,
                text=_page_text_value(page),
                source=page.source,
                quality_score=getattr(page, "quality_score", None),
                words=getattr(page, "words", None),
            )
        )
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
    checkpoint = _get_task_run_checkpoint(db, run_id=run_id)
    resume_current = _resume_stage_current(
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

    _set_task_checkpoint(
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
    for start in range(start_index, len(chunks), batch_size):
        chunk_batch = chunks[start : start + batch_size]
        texts = [str(chunk["text"]) for chunk in chunk_batch]
        vectors = embed_texts(settings, texts, telemetry=telemetry)
        points = []
        for offset, (chunk, vector) in enumerate(zip(chunk_batch, vectors)):
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
        _set_task_checkpoint(
            db,
            run_id=run_id,
            stage="embedding_chunks",
            current=min(start + len(chunk_batch), len(chunks)),
            total=len(chunks),
            extra={"source": embedding_source, "batch_size": batch_size, **telemetry},
        )

    existing = db.get(DocumentEmbedding, doc.id)
    if not existing:
        existing = DocumentEmbedding(doc_id=doc.id)
        db.add(existing)
    existing.content_hash = content_hash
    existing.embedding_model = settings.embedding_model
    existing.embedded_at = datetime.now(timezone.utc).isoformat()
    previous_source = str(existing.embedding_source or "").strip().lower()
    if previous_source == "both" or (previous_source and previous_source != embedding_source):
        existing.embedding_source = "both"
    else:
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


def _process_doc(settings, db: Session, doc_id: int, run_id: int | None = None) -> None:
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
    _process_evidence_index(settings, db, doc_id, run_id=run_id)
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
    _embed_with_pages(
        settings,
        db,
        doc,
        baseline_pages,
        vision_pages,
        "vision" if vision_pages else "paperless",
        run_id=run_id,
    )

    if _is_large_doc(settings, doc):
        _process_page_notes(settings, db, doc_id, source="paperless_ocr", run_id=run_id)
        if vision_pages:
            _process_page_notes(settings, db, doc_id, source="vision_ocr", run_id=run_id)
            _process_summary_hierarchical(settings, db, doc_id, source="vision_ocr", run_id=run_id)
        else:
            _process_summary_hierarchical(settings, db, doc_id, source="paperless_ocr", run_id=run_id)

    # Suggestions
    tags = get_cached_tags(settings)
    correspondents = get_cached_correspondents(settings)
    baseline_text = doc.content or ""
    if _is_large_doc(settings, doc):
        distilled = _build_distilled_context_from_hier_summary(
            db,
            doc_id=doc_id,
            source="paperless_ocr",
            max_chars=settings.worker_suggestions_max_chars,
        )
        if not distilled:
            distilled = _build_distilled_context_from_page_notes(
                db,
                doc_id=doc_id,
                source="paperless_ocr",
                max_chars=settings.worker_suggestions_max_chars,
            )
        if distilled:
            baseline_text = distilled
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
        vision_text = ""
        if _is_large_doc(settings, doc):
            vision_text = _build_distilled_context_from_hier_summary(
                db,
                doc_id=doc_id,
                source="vision_ocr",
                max_chars=settings.worker_suggestions_max_chars,
            )
        if not vision_text:
            vision_text = _build_distilled_context_from_page_notes(
                db,
                doc_id=doc_id,
                source="vision_ocr",
                max_chars=settings.worker_suggestions_max_chars,
            )
        if not vision_text:
            vision_text = _join_page_texts_limited(
                vision_pages,
                max_chars=settings.worker_suggestions_max_chars,
            )
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

def _process_vision_ocr_only(settings, db: Session, doc_id: int, force: bool = False, run_id: int | None = None) -> None:
    if is_cancel_requested(settings):
        logger.info("Worker cancel requested; abort vision OCR doc=%s", doc_id)
        return
    doc = get_document_or_none(db, doc_id)
    if not doc:
        return
    if not settings.enable_vision_ocr:
        logger.info("Vision OCR disabled; skipping doc=%s", doc_id)
        return
    if not settings.vision_model:
        logger.warning("VISION_MODEL not set; skipping vision OCR doc=%s", doc_id)
        return

    existing_pages = {
        int(row.page)
        for row in db.query(DocumentPageText.page)
        .filter(DocumentPageText.doc_id == doc_id, DocumentPageText.source == "vision_ocr")
        .all()
    }
    expected_pages = int(doc.page_count or 0)
    if expected_pages > 0:
        if force:
            target_pages = list(range(1, expected_pages + 1))
        else:
            target_pages = [page for page in range(1, expected_pages + 1) if page not in existing_pages]
            if not target_pages:
                ensure_document_ocr_score(settings, db, doc, "vision_ocr")
                logger.info("Vision OCR skipped (already complete) doc=%s pages=%s", doc_id, expected_pages)
                return
    else:
        if not force and existing_pages:
            ensure_document_ocr_score(settings, db, doc, "vision_ocr")
            logger.info("Vision OCR skipped (cached; unknown page_count) doc=%s", doc_id)
            return
        target_pages = None

    pdf_bytes = fetch_pdf_bytes_for_doc(settings, doc)
    configured_batch_size = max(1, int(settings.vision_ocr_batch_pages or VISION_OCR_BATCH_DEFAULT))
    if settings.vision_ocr_max_pages > 0:
        batch_size = min(configured_batch_size, settings.vision_ocr_max_pages)
    else:
        batch_size = configured_batch_size

    total_pages = len(target_pages) if target_pages is not None else int(doc.page_count or 0)
    batch_size = _vision_ocr_batch_size(
        total_pages=max(0, int(total_pages)),
        configured_batch_size=max(1, int(batch_size)),
    )
    logger.info(
        "Vision OCR start doc=%s expected_pages=%s existing_pages=%s remaining=%s batch_size=%s force=%s",
        doc_id,
        doc.page_count,
        len(existing_pages),
        total_pages if total_pages > 0 else "unknown",
        batch_size,
        force,
    )

    processed_any = False
    if target_pages is None:
        _set_task_checkpoint(db, run_id=run_id, stage="vision_ocr", current=0, total=0, extra={"mode": "all"})
        generated = vision_ocr.ocr_pdf_pages(
            settings,
            pdf_bytes,
            page_numbers=None,
        )
        if generated:
            upsert_page_texts(
                db,
                settings,
                doc_id,
                generated,
                source_filter="vision_ocr",
                replace_pages=[page.page for page in generated],
            )
            processed_any = True
    else:
        checkpoint = _get_task_run_checkpoint(db, run_id=run_id)
        resume_current = _resume_stage_current(
            checkpoint,
            stage="vision_ocr",
            total=len(target_pages),
        )
        start_index = max(0, min(resume_current, len(target_pages)))
        if start_index > 0:
            logger.info(
                "Vision OCR resume doc=%s start=%s total=%s",
                doc_id,
                start_index,
                len(target_pages),
            )
        processed = start_index
        _set_task_checkpoint(
            db,
            run_id=run_id,
            stage="vision_ocr",
            current=processed,
            total=len(target_pages),
            extra={"mode": "pages", "batch_size": batch_size, "resumed": start_index > 0},
        )
        for start in range(start_index, len(target_pages), batch_size):
            if is_cancel_requested(settings):
                logger.info(
                    "Worker cancel requested; stop vision OCR doc=%s processed=%s/%s",
                    doc_id,
                    processed,
                    len(target_pages),
                )
                break
            batch_pages = target_pages[start : start + batch_size]
            generated = vision_ocr.ocr_pdf_pages(
                settings,
                pdf_bytes,
                page_numbers=batch_pages,
            )
            if generated:
                upsert_page_texts(
                    db,
                    settings,
                    doc_id,
                    generated,
                    source_filter="vision_ocr",
                    replace_pages=[page.page for page in generated],
                )
                processed_any = True
            processed += len(batch_pages)
            logger.info(
                "Vision OCR progress doc=%s processed=%s/%s",
                doc_id,
                processed,
                len(target_pages),
            )
            _set_task_checkpoint(
                db,
                run_id=run_id,
                stage="vision_ocr",
                current=processed,
                total=len(target_pages),
                extra={"mode": "pages", "batch_size": batch_size},
            )

    if processed_any:
        ensure_document_ocr_score(settings, db, doc, "vision_ocr", force=force)


def _process_cleanup_texts(
    settings,
    db: Session,
    doc_id: int,
    *,
    source: str | None = None,
    clear_first: bool = False,
) -> None:
    if is_cancel_requested(settings):
        logger.info("Worker cancel requested; abort cleanup texts doc=%s", doc_id)
        return
    reclean_page_texts(
        db,
        settings,
        doc_id=doc_id,
        source=source,
        clear_first=clear_first,
    )


def _process_page_notes(settings, db: Session, doc_id: int, source: str, run_id: int | None = None) -> None:
    if is_cancel_requested(settings):
        logger.info("Worker cancel requested; abort page notes doc=%s source=%s", doc_id, source)
        return
    doc = get_document_or_none(db, doc_id)
    if not doc:
        return
    if not _is_large_doc(settings, doc):
        logger.info("Page notes skipped (small doc) doc=%s threshold=%s", doc_id, settings.large_doc_page_threshold)
        return
    if source == "paperless_ocr":
        _ensure_paperless_page_texts(settings, db, doc)
    pages = (
        db.query(DocumentPageText)
        .filter(DocumentPageText.doc_id == doc_id, DocumentPageText.source == source)
        .order_by(DocumentPageText.page.asc())
        .all()
    )
    if not pages:
        logger.info("Page notes skipped (no pages) doc=%s source=%s", doc_id, source)
        return
    checkpoint = _get_task_run_checkpoint(db, run_id=run_id)
    resume_current = _resume_stage_current(
        checkpoint,
        stage="page_notes",
        source=source,
        total=len(pages),
    )
    start_index = max(0, min(resume_current, len(pages)))
    if start_index > 0:
        logger.info(
            "Page notes resume doc=%s source=%s start=%s total=%s",
            doc_id,
            source,
            start_index,
            len(pages),
        )
    _set_task_checkpoint(
        db,
        run_id=run_id,
        stage="page_notes",
        current=start_index,
        total=len(pages),
        extra={"source": source, "resumed": start_index > 0},
    )
    processed_pages = start_index
    for page in pages[start_index:]:
        if is_cancel_requested(settings):
            logger.info("Worker cancel requested; stop page notes doc=%s source=%s", doc_id, source)
            return
        text = _page_text_value(page).strip()
        if not text:
            upsert_page_note(
                db,
                doc_id=doc_id,
                page=int(page.page),
                source=source,
                payload=None,
                status="skipped",
                error="empty_page_text",
                model_name=settings.text_model,
            )
            continue
        try:
            payload = generate_page_notes(
                settings,
                page=int(page.page),
                text=text,
            )
            upsert_page_note(
                db,
                doc_id=doc_id,
                page=int(page.page),
                source=source,
                payload=payload,
                status="ok",
                model_name=settings.text_model,
            )
        except Exception as exc:
            upsert_page_note(
                db,
                doc_id=doc_id,
                page=int(page.page),
                source=source,
                payload=None,
                status="error",
                error=str(exc)[:1000],
                model_name=settings.text_model,
            )
            logger.warning("Page notes failed doc=%s page=%s source=%s error=%s", doc_id, page.page, source, exc)
        finally:
            processed_pages += 1
            _set_task_checkpoint(
                db,
                run_id=run_id,
                stage="page_notes",
                current=processed_pages,
                total=len(pages),
                extra={"source": source},
            )


def _process_summary_hierarchical(settings, db: Session, doc_id: int, source: str, run_id: int | None = None) -> None:
    if is_cancel_requested(settings):
        logger.info("Worker cancel requested; abort hierarchical summary doc=%s", doc_id)
        return
    doc = get_document_or_none(db, doc_id)
    if not doc:
        return
    if not _is_large_doc(settings, doc):
        logger.info("Hierarchical summary skipped (small doc) doc=%s", doc_id)
        return
    note_rows = (
        db.query(DocumentPageNote)
        .filter(
            DocumentPageNote.doc_id == doc_id,
            DocumentPageNote.source == source,
            DocumentPageNote.status == "ok",
        )
        .order_by(DocumentPageNote.page.asc())
        .all()
    )
    if not note_rows and source != "paperless_ocr":
        note_rows = (
            db.query(DocumentPageNote)
            .filter(
                DocumentPageNote.doc_id == doc_id,
                DocumentPageNote.source == "paperless_ocr",
                DocumentPageNote.status == "ok",
            )
            .order_by(DocumentPageNote.page.asc())
            .all()
        )
        source = "paperless_ocr"
    if not note_rows:
        logger.info("Hierarchical summary skipped (no page notes) doc=%s", doc_id)
        return

    page_to_note: dict[int, dict] = {}
    for row in note_rows:
        raw = (row.notes_text or "").strip()
        if not raw:
            continue
        page_to_note[int(row.page)] = {"page": int(row.page), "text": raw}
    sections = group_notes_into_sections(
        sorted(page_to_note.items(), key=lambda item: item[0]),
        max_pages=settings.summary_section_pages,
        max_input_tokens=settings.section_summary_max_input_tokens,
    )
    checkpoint = _get_task_run_checkpoint(db, run_id=run_id)
    resume_current = _resume_stage_current(
        checkpoint,
        stage="summary_sections",
        source=source,
        total=len(sections),
    )
    start_index = max(0, min(resume_current, len(sections)))
    persisted_by_key: dict[str, dict] = {}
    if start_index > 0:
        persisted_rows = (
            db.query(DocumentSectionSummary)
            .filter(
                DocumentSectionSummary.doc_id == doc_id,
                DocumentSectionSummary.source == source,
                DocumentSectionSummary.status == "ok",
            )
            .all()
        )
        for row in persisted_rows:
            raw_summary = (row.summary_text or "").strip()
            if not raw_summary:
                continue
            persisted_by_key[str(row.section_key)] = {
                "section": str(row.section_key),
                "text": raw_summary,
                "summary": raw_summary,
                "key_facts": [],
                "key_dates": [],
                "key_entities": [],
                "key_numbers": [],
                "open_questions": [],
                "confidence_notes": [],
            }
        required_keys = [str(sections[i][0]) for i in range(start_index)]
        if not all(key in persisted_by_key for key in required_keys):
            logger.info(
                "Summary resume reset doc=%s source=%s reason=missing_persisted_sections",
                doc_id,
                source,
            )
            start_index = 0
            persisted_by_key = {}
        else:
            logger.info(
                "Summary resume doc=%s source=%s start=%s total=%s",
                doc_id,
                source,
                start_index,
                len(sections),
            )
    _set_task_checkpoint(
        db,
        run_id=run_id,
        stage="summary_sections",
        current=start_index,
        total=len(sections),
        extra={"source": source, "resumed": start_index > 0},
    )
    section_payloads: list[tuple[str, dict]] = []
    if start_index > 0:
        for section_key, _ in sections[:start_index]:
            cached = persisted_by_key.get(str(section_key))
            if cached is not None:
                section_payloads.append((section_key, cached))
    for section_index, (section_key, page_notes) in enumerate(sections[start_index:], start=start_index + 1):
        if is_cancel_requested(settings):
            logger.info("Worker cancel requested; stop section summaries doc=%s", doc_id)
            return
        if not page_notes:
            continue
        try:
            section_summary = generate_section_summary(
                settings,
                section_key=section_key,
                page_notes=page_notes,
            )
            section_payloads.append((section_key, section_summary))
        except Exception as exc:
            logger.warning("Section summary failed doc=%s section=%s error=%s", doc_id, section_key, exc)
        finally:
            _set_task_checkpoint(
                db,
                run_id=run_id,
                stage="summary_sections",
                current=section_index,
                total=len(sections),
                extra={"source": source},
            )
    if not section_payloads:
        return
    replace_section_summaries(
        db,
        doc_id=doc_id,
        source=source,
        summaries=section_payloads,
        model_name=settings.text_model,
    )
    global_payload: dict
    try:
        global_payload = generate_global_summary(
            settings,
            section_summaries=[payload for _, payload in section_payloads],
        )
    except Exception as exc:
        global_payload = {
            "summary": "",
            "executive_summary": "",
            "key_facts": [],
            "key_dates": [],
            "key_entities": [],
            "key_numbers": [],
            "open_questions": [],
            "confidence_notes": [f"global_summary_error:{str(exc)[:200]}"],
        }
    global_payload["source"] = source
    persist_suggestions(
        db,
        doc_id,
        "hier_summary",
        global_payload,
        model_name=settings.text_model,
        action="hierarchical_summary_generate",
    )

def _process_embeddings_paperless(settings, db: Session, doc_id: int, run_id: int | None = None) -> None:
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
    _embed_with_pages(settings, db, doc, baseline_pages, [], "paperless", run_id=run_id)


def _process_evidence_index(
    settings,
    db: Session,
    doc_id: int,
    *,
    source: str = "paperless_pdf",
    run_id: int | None = None,
) -> None:
    if is_cancel_requested(settings):
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
    _set_task_checkpoint(
        db,
        run_id=run_id,
        stage="evidence_index",
        current=len(rows),
        total=len(rows),
        extra={"source": source},
    )
    upsert_page_anchors(db, doc_id=doc_id, source=source, rows=rows)


def _process_embeddings_vision(settings, db: Session, doc_id: int, run_id: int | None = None) -> None:
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
    _embed_with_pages(settings, db, doc, baseline_pages, vision_pages, "vision", run_id=run_id)


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
    baseline_text = clean_ocr_text(doc.content or "")
    if _is_large_doc(settings, doc):
        distilled = _build_distilled_context_from_hier_summary(
            db,
            doc_id=doc_id,
            source="paperless_ocr",
            max_chars=settings.worker_suggestions_max_chars,
        )
        if not distilled:
            distilled = _build_distilled_context_from_page_notes(
                db,
                doc_id=doc_id,
                source="paperless_ocr",
                max_chars=settings.worker_suggestions_max_chars,
            )
        if distilled:
            baseline_text = distilled
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
    doc = get_document_or_none(db, doc_id)
    if not doc:
        return
    vision_pages = (
        db.query(DocumentPageText)
        .filter(DocumentPageText.doc_id == doc_id, DocumentPageText.source == "vision_ocr")
        .order_by(DocumentPageText.page.asc())
        .all()
    )
    expected_pages = int(doc.page_count or 0)
    bounded_pages = {int(page.page) for page in vision_pages if int(page.page) > 0}
    has_complete_vision = bool(vision_pages) if expected_pages <= 0 else len(bounded_pages) >= expected_pages
    if settings.enable_vision_ocr and not has_complete_vision:
        logger.info(
            "Vision suggestions requested without complete vision OCR; backfilling doc=%s expected_pages=%s have=%s",
            doc_id,
            expected_pages if expected_pages > 0 else "unknown",
            len(bounded_pages),
        )
        _process_vision_ocr_only(settings, db, doc_id, force=False)
        vision_pages = (
            db.query(DocumentPageText)
            .filter(DocumentPageText.doc_id == doc_id, DocumentPageText.source == "vision_ocr")
            .order_by(DocumentPageText.page.asc())
            .all()
        )
    if not vision_pages:
        raise RuntimeError(f"vision_suggestions_missing_pages doc_id={doc_id}")

    vision_text = ""
    if _is_large_doc(settings, doc):
        vision_text = _build_distilled_context_from_hier_summary(
            db,
            doc_id=doc_id,
            source="vision_ocr",
            max_chars=settings.worker_suggestions_max_chars,
        )
    if not vision_text:
        vision_text = _build_distilled_context_from_page_notes(
            db,
            doc_id=doc_id,
            source="vision_ocr",
            max_chars=settings.worker_suggestions_max_chars,
        )
    if not vision_text:
        vision_text = _join_page_texts_limited(
            vision_pages,
            max_chars=settings.worker_suggestions_max_chars,
        )
    if not vision_text:
        raise RuntimeError(f"vision_suggestions_empty_text doc_id={doc_id}")

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
        text = _join_page_texts_limited(vision_pages, max_chars=settings.worker_suggestions_max_chars)
    else:
        doc = get_document_or_none(db, doc_id)
        text = clean_ocr_text(doc.content) if doc and doc.content else ""
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


def _dispatch_task(
    settings,
    db: Session,
    task_type: str,
    doc_id: int,
    task: dict | None,
    *,
    run_id: int | None = None,
) -> None:
    handlers = {
        "sync": lambda: _process_sync_only(settings, db, doc_id),
        "evidence_index": lambda: _process_evidence_index(
            settings,
            db,
            doc_id,
            source=str((task or {}).get("source") or "paperless_pdf"),
            run_id=run_id,
        ),
        "embeddings_paperless": lambda: _process_embeddings_paperless(settings, db, doc_id, run_id=run_id),
        "embeddings_vision": lambda: _process_embeddings_vision(settings, db, doc_id, run_id=run_id),
        "cleanup_texts": lambda: _process_cleanup_texts(
            settings,
            db,
            doc_id,
            source=str((task or {}).get("source")) if (task or {}).get("source") else None,
            clear_first=bool((task or {}).get("clear_first")),
        ),
        "page_notes_paperless": lambda: _process_page_notes(settings, db, doc_id, "paperless_ocr", run_id=run_id),
        "page_notes_vision": lambda: _process_page_notes(settings, db, doc_id, "vision_ocr", run_id=run_id),
        "summary_hierarchical": lambda: _process_summary_hierarchical(
            settings,
            db,
            doc_id,
            str((task or {}).get("source") or "vision_ocr"),
            run_id=run_id,
        ),
        "suggestions_paperless": lambda: _process_suggestions_paperless(settings, db, doc_id),
        "suggestions_vision": lambda: _process_suggestions_vision(settings, db, doc_id),
        "suggest_field": lambda: _process_suggest_field(settings, db, task or {}),
    }
    if task_type == "vision_ocr":
        force = bool(task.get("force")) if isinstance(task, dict) else False
        _process_vision_ocr_only(settings, db, doc_id, force=force, run_id=run_id)
        return
    handler = handlers.get(task_type)
    if handler:
        handler()
        return
    _process_doc(settings, db, doc_id, run_id=run_id)


def _handle_worker_cancel_request(settings) -> bool:
    if not is_cancel_requested(settings):
        return False
    logger.info("Worker cancel requested; clearing queue")
    clear_queue(settings)
    reset_stats(settings)
    clear_cancel(settings)
    return True


def main() -> None:
    settings = load_settings()
    configure_logging(settings, service="worker")
    if not settings.queue_enabled:
        raise SystemExit("QUEUE_ENABLED is not set")
    client = _get_client(settings)
    if not client:
        raise SystemExit("Redis not configured")
    worker_token = f"{socket.gethostname()}:{os.getpid()}:{int(time.time())}"
    while not acquire_worker_lock(settings, worker_token):
        logger.warning("Worker lock unavailable or Redis not ready; retrying in 5s")
        time.sleep(5)
    clear_running_task(settings)
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

    def _heartbeat_refresher() -> None:
        while not stop_event.is_set():
            try:
                mark_worker_heartbeat(settings)
            except Exception:
                logger.warning("Worker heartbeat update failed", exc_info=True)
            stop_event.wait(HEARTBEAT_INTERVAL_SECONDS)

    lock_refresher = threading.Thread(target=_lock_refresher, name="worker-lock-refresher", daemon=True)
    heartbeat_refresher = threading.Thread(
        target=_heartbeat_refresher,
        name="worker-heartbeat-refresher",
        daemon=True,
    )
    lock_refresher.start()
    heartbeat_refresher.start()
    try:
        while True:
            if lock_lost.is_set():
                raise SystemExit("Worker lock lost; exiting")
            if is_paused(settings):
                time.sleep(0.5)
                continue
            move_due_delayed_tasks(settings, limit=100)
            if _handle_worker_cancel_request(settings):
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
            if _handle_worker_cancel_request(settings):
                logger.info("Worker cancel requested; skipping doc=%s", doc_id)
                time.sleep(0.5)
                continue
            running_task = task if isinstance(task, dict) else {"doc_id": doc_id, "task": "full"}
            set_running_task(settings, running_task)
            mark_in_progress(settings)
            run_started = time.time()
            run_id: int | None = None
            run_status = "completed"
            run_error_type: str | None = None
            run_error_message: str | None = None
            pending_retry_payload: dict | None = None
            pending_retry_delay_seconds: int | None = None
            pending_dead_letter: dict | None = None
            retry_attempt = 0
            if isinstance(task, dict):
                try:
                    retry_attempt = int(task.get("retry_count") or 0)
                except Exception:
                    retry_attempt = 0
            try:
                with SessionLocal() as db:
                    task_payload = task if isinstance(task, dict) else {"doc_id": doc_id, "task": task_type}
                    source = task_source_from_payload(task if isinstance(task, dict) else None)
                    run_row = create_task_run(
                        db,
                        doc_id=doc_id,
                        task=task_type,
                        source=source,
                        payload=task_payload,
                        worker_id=worker_token,
                        attempt=retry_attempt + 1,
                    )
                    run_id = int(run_row.id)
                    if retry_attempt > 0:
                        previous_checkpoint = find_latest_checkpoint(
                            db,
                            doc_id=doc_id,
                            task=task_type,
                            source=source,
                        )
                        if previous_checkpoint:
                            _set_task_checkpoint(
                                db,
                                run_id=run_id,
                                stage="resume",
                                extra={"resume_from": previous_checkpoint},
                            )
                    try:
                        _dispatch_task(
                            settings,
                            db,
                            task_type,
                            doc_id,
                            task if isinstance(task, dict) else None,
                            run_id=run_id,
                        )
                    except Exception as exc:
                        _safe_rollback(db, context="dispatch_task_failed")
                        run_status = "failed"
                        run_error_type = classify_worker_error(exc)
                        run_error_message = str(exc)
                        log_event(
                            logger,
                            logging.ERROR,
                            "Worker task failed",
                            doc_id=doc_id,
                            task=task_type,
                            retry_attempt=retry_attempt + 1,
                            error_type=run_error_type,
                            error_message=run_error_message,
                        )
                        logger.exception("Worker failed doc=%s error=%s", doc_id, exc)
                    finally:
                        duration_ms = int(max(0.0, (time.time() - run_started) * 1000))
                        should_retry = bool(
                            run_status == "failed"
                            and run_error_type
                            and is_retryable_error_type(run_error_type)
                            and retry_attempt < settings.worker_max_retries
                            and isinstance(task_payload, dict)
                        )
                        if should_retry:
                            retry_payload = dict(task_payload)
                            retry_payload["retry_count"] = retry_attempt + 1
                            pending_retry_payload = retry_payload
                            pending_retry_delay_seconds = min(300, 5 * (2 ** retry_attempt))
                            run_status = "retrying"
                            log_event(
                                logger,
                                logging.WARNING,
                                "Worker task requeued",
                                doc_id=doc_id,
                                task=task_type,
                                retry_attempt=retry_attempt + 1,
                                max_retries=settings.worker_max_retries,
                                error_type=run_error_type,
                            )
                        elif run_status == "failed":
                            pending_dead_letter = {
                                "task": task_payload if isinstance(task_payload, dict) else {"doc_id": doc_id, "task": task_type},
                                "error_type": run_error_type or "WORKER_TASK_ERROR",
                                "error_message": run_error_message or "unknown error",
                                "attempt": retry_attempt + 1,
                            }
                        if run_id is not None:
                            _safe_rollback(db, context="before_finish_task_run")
                            finish_task_run(
                                db,
                                run_id=run_id,
                                status=run_status,
                                duration_ms=duration_ms,
                                error_type=run_error_type,
                                error_message=run_error_message,
                            )
            except Exception as exc:
                log_event(
                    logger,
                    logging.ERROR,
                    "Worker loop task bookkeeping failed",
                    doc_id=doc_id,
                    task=task_type,
                    error_type=classify_worker_error(exc),
                    error_message=str(exc),
                )
                logger.exception("Worker bookkeeping failed doc=%s task=%s", doc_id, task_type)
            finally:
                clear_running_task(settings)
                mark_done(settings)
                record_last_run(settings, time.time() - run_started)
                if client:
                    if isinstance(task, dict):
                        client.srem(QUEUE_SET, task_key(task))
                    else:
                        client.srem(QUEUE_SET, str(doc_id))
                if pending_retry_payload is not None:
                    enqueue_task_delayed(settings, pending_retry_payload, pending_retry_delay_seconds or 5)
                elif pending_dead_letter is not None:
                    add_dead_letter(
                        settings,
                        task=pending_dead_letter["task"],
                        error_type=str(pending_dead_letter["error_type"]),
                        error_message=str(pending_dead_letter["error_message"]),
                        attempt=int(pending_dead_letter["attempt"]),
                    )
    finally:
        stop_event.set()
        clear_running_task(settings)
        release_worker_lock(settings, worker_token)


if __name__ == "__main__":
    main()

