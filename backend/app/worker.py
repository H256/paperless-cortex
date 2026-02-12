from __future__ import annotations

import logging
import os
import socket
import threading
import time
from collections.abc import Iterable

from sqlalchemy.orm import Session

from app.config import load_settings
from app.db import SessionLocal
from app.models import Document, DocumentEmbedding, DocumentPageNote, DocumentPageText, DocumentSuggestion, SyncState
from app.services import paperless
from app.services.documents import fetch_pdf_bytes_for_doc, get_document_or_none
from app.services.embeddings import (
    chunk_document_with_pages,
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
import json

logger = logging.getLogger(__name__)
HEARTBEAT_INTERVAL_SECONDS = 5
VISION_OCR_BATCH_DEFAULT = 25


def _page_text_value(page: object) -> str:
    clean_text = getattr(page, "clean_text", None)
    if isinstance(clean_text, str) and clean_text.strip():
        return clean_text
    raw_text = getattr(page, "text", None)
    if isinstance(raw_text, str):
        return clean_ocr_text(raw_text)
    return ""


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
        payload = row.notes_json or ""
        if not payload:
            continue
        block = f"Page {row.page}: {payload}"
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

    blocks: list[str] = []
    executive = str(payload.get("executive_summary") or "").strip()
    summary = str(payload.get("summary") or "").strip()
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


def _embed_with_pages(settings, db: Session, doc: Document, baseline_pages, vision_pages, embedding_source: str) -> None:
    content_value = clean_ocr_text(doc.content or "")
    page_texts = (baseline_pages or []) + (vision_pages or [])
    hash_source = (
        "\f".join(f"{page.source}:{_page_text_value(page)}" for page in page_texts)
        if page_texts
        else content_value
    )
    content_hash = __import__("hashlib").sha256((hash_source or "").encode("utf-8")).hexdigest()

    ensure_embedding_collection(settings)
    delete_points_for_doc(settings, doc.id)
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
    chunks = baseline_chunks + vision_chunks
    max_chunks = max(0, int(settings.embedding_max_chunks_per_doc))
    if max_chunks > 0 and len(chunks) > max_chunks:
        logger.warning(
            "Embedding chunks capped doc=%s chunks=%s cap=%s",
            doc.id,
            len(chunks),
            max_chunks,
        )
        chunks = chunks[:max_chunks]

    batch_size = max(1, int(settings.embedding_batch_size))
    for start in range(0, len(chunks), batch_size):
        chunk_batch = chunks[start : start + batch_size]
        texts = [str(chunk["text"]) for chunk in chunk_batch]
        vectors = embed_texts(settings, texts)
        points = []
        for offset, (chunk, vector) in enumerate(zip(chunk_batch, vectors)):
            chunk_idx = start + offset
            chunk_text_value = texts[offset]
            points.append(
                {
                    "id": make_point_id(doc.id, chunk_idx),
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
    _embed_with_pages(
        settings,
        db,
        doc,
        baseline_pages,
        vision_pages,
        "vision" if vision_pages else "paperless",
    )

    if _is_large_doc(settings, doc):
        _process_page_notes(settings, db, doc_id, source="paperless_ocr")
        if vision_pages:
            _process_page_notes(settings, db, doc_id, source="vision_ocr")
            _process_summary_hierarchical(settings, db, doc_id, source="vision_ocr")
        else:
            _process_summary_hierarchical(settings, db, doc_id, source="paperless_ocr")

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

def _process_vision_ocr_only(settings, db: Session, doc_id: int, force: bool = False) -> None:
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
        processed = 0
        for start in range(0, len(target_pages), batch_size):
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


def _process_page_notes(settings, db: Session, doc_id: int, source: str) -> None:
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
    for page in pages:
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


def _process_summary_hierarchical(settings, db: Session, doc_id: int, source: str) -> None:
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
        try:
            payload = json.loads(row.notes_json or "{}")
            if isinstance(payload, dict):
                page_to_note[int(row.page)] = payload
        except Exception:
            continue
    sections = group_notes_into_sections(
        sorted(page_to_note.items(), key=lambda item: item[0]),
        max_pages=settings.summary_section_pages,
        max_input_tokens=settings.section_summary_max_input_tokens,
    )
    section_payloads: list[tuple[str, dict]] = []
    for section_key, page_notes in sections:
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
    vision_pages = (
        db.query(DocumentPageText)
        .filter(DocumentPageText.doc_id == doc_id, DocumentPageText.source == "vision_ocr")
        .order_by(DocumentPageText.page.asc())
        .all()
    )
    if vision_pages:
        vision_text = ""
        if doc and _is_large_doc(settings, doc):
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


def _dispatch_task(settings, db: Session, task_type: str, doc_id: int, task: dict | None) -> None:
    handlers = {
        "sync": lambda: _process_sync_only(settings, db, doc_id),
        "embeddings_paperless": lambda: _process_embeddings_paperless(settings, db, doc_id),
        "embeddings_vision": lambda: _process_embeddings_vision(settings, db, doc_id),
        "cleanup_texts": lambda: _process_cleanup_texts(
            settings,
            db,
            doc_id,
            source=str((task or {}).get("source")) if (task or {}).get("source") else None,
            clear_first=bool((task or {}).get("clear_first")),
        ),
        "page_notes_paperless": lambda: _process_page_notes(settings, db, doc_id, "paperless_ocr"),
        "page_notes_vision": lambda: _process_page_notes(settings, db, doc_id, "vision_ocr"),
        "summary_hierarchical": lambda: _process_summary_hierarchical(
            settings,
            db,
            doc_id,
            str((task or {}).get("source") or "vision_ocr"),
        ),
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
            running_task = task if isinstance(task, dict) else {"doc_id": doc_id, "task": "full"}
            set_running_task(settings, running_task)
            mark_in_progress(settings)
            run_started = time.time()
            try:
                with SessionLocal() as db:
                    _dispatch_task(settings, db, task_type, doc_id, task if isinstance(task, dict) else None)
            except Exception as exc:
                logger.exception("Worker failed doc=%s error=%s", doc_id, exc)
            finally:
                clear_running_task(settings)
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
