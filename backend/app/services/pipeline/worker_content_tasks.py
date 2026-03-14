from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import httpx

from app.models import Document, DocumentPageText
from app.services.ai import vision_ocr
from app.services.ai.hierarchical_summary import (
    generate_page_notes,
    is_large_document,
    upsert_page_note,
)
from app.services.ai.hierarchical_summary_pipeline import HierarchicalSummaryPipeline
from app.services.ai.ocr_scoring import ensure_document_ocr_score
from app.services.documents.documents import fetch_pdf_bytes_for_doc, get_document_or_none
from app.services.documents.page_text_store import upsert_page_texts
from app.services.documents.text_cleaning import clean_ocr_text
from app.services.documents.text_pages import get_baseline_page_texts
from app.services.pipeline.worker_checkpoint import (
    get_task_run_checkpoint,
    resume_stage_current,
    set_task_checkpoint,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.orm import Session

    from app.config import Settings

logger = logging.getLogger(__name__)
VISION_OCR_BATCH_DEFAULT = 25


def _page_text_value(page: object) -> str:
    clean_text = getattr(page, "clean_text", None)
    if isinstance(clean_text, str) and clean_text.strip():
        return clean_text
    raw_text = getattr(page, "text", None)
    if isinstance(raw_text, str):
        return clean_ocr_text(raw_text)
    return ""


def _vision_ocr_batch_size(
    *,
    total_pages: int,
    configured_batch_size: int,
) -> int:
    if total_pages >= 300:
        return min(configured_batch_size, 5)
    if total_pages >= 120:
        return min(configured_batch_size, 10)
    return configured_batch_size


def ensure_paperless_page_texts(settings: Settings, db: Session, doc: Document) -> None:
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


def process_vision_ocr_only(
    settings: Settings,
    db: Session,
    doc_id: int,
    *,
    force: bool = False,
    run_id: int | None = None,
    is_cancel_requested_fn: Callable[[Settings], bool],
) -> None:
    if is_cancel_requested_fn(settings):
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
            target_pages = [
                page for page in range(1, expected_pages + 1) if page not in existing_pages
            ]
            if not target_pages:
                ensure_document_ocr_score(settings, db, doc, "vision_ocr")
                logger.info(
                    "Vision OCR skipped (already complete) doc=%s pages=%s", doc_id, expected_pages
                )
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
        set_task_checkpoint(
            db, run_id=run_id, stage="vision_ocr", current=0, total=0, extra={"mode": "all"}
        )
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
        checkpoint = get_task_run_checkpoint(db, run_id=run_id)
        resume_current = resume_stage_current(
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
        set_task_checkpoint(
            db,
            run_id=run_id,
            stage="vision_ocr",
            current=processed,
            total=len(target_pages),
            extra={"mode": "pages", "batch_size": batch_size, "resumed": start_index > 0},
        )
        for start in range(start_index, len(target_pages), batch_size):
            if is_cancel_requested_fn(settings):
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
            set_task_checkpoint(
                db,
                run_id=run_id,
                stage="vision_ocr",
                current=processed,
                total=len(target_pages),
                extra={"mode": "pages", "batch_size": batch_size},
            )

    if processed_any:
        ensure_document_ocr_score(settings, db, doc, "vision_ocr", force=force)


def process_page_notes(
    settings: Settings,
    db: Session,
    doc_id: int,
    source: str,
    *,
    run_id: int | None = None,
    is_cancel_requested_fn: Callable[[Settings], bool],
) -> None:
    if is_cancel_requested_fn(settings):
        logger.info("Worker cancel requested; abort page notes doc=%s source=%s", doc_id, source)
        return
    doc = get_document_or_none(db, doc_id)
    if not doc:
        return
    if not is_large_document(
        page_count=doc.page_count,
        total_text=doc.content,
        threshold_pages=settings.large_doc_page_threshold,
    ):
        logger.info(
            "Page notes skipped (small doc) doc=%s threshold=%s",
            doc_id,
            settings.large_doc_page_threshold,
        )
        return
    if source == "paperless_ocr":
        ensure_paperless_page_texts(settings, db, doc)
    pages = (
        db.query(DocumentPageText)
        .filter(DocumentPageText.doc_id == doc_id, DocumentPageText.source == source)
        .order_by(DocumentPageText.page.asc())
        .all()
    )
    if not pages:
        logger.info("Page notes skipped (no pages) doc=%s source=%s", doc_id, source)
        return
    checkpoint = get_task_run_checkpoint(db, run_id=run_id)
    resume_current = resume_stage_current(
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
    set_task_checkpoint(
        db,
        run_id=run_id,
        stage="page_notes",
        current=start_index,
        total=len(pages),
        extra={"source": source, "resumed": start_index > 0},
    )
    processed_pages = start_index
    for page in pages[start_index:]:
        if is_cancel_requested_fn(settings):
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
        except (RuntimeError, ValueError, httpx.HTTPError) as exc:
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
            logger.warning(
                "Page notes failed doc=%s page=%s source=%s error=%s",
                doc_id,
                page.page,
                source,
                exc,
            )
        finally:
            processed_pages += 1
            set_task_checkpoint(
                db,
                run_id=run_id,
                stage="page_notes",
                current=processed_pages,
                total=len(pages),
                extra={"source": source},
            )


def process_summary_hierarchical(
    settings: Settings,
    db: Session,
    doc_id: int,
    source: str,
    *,
    run_id: int | None = None,
) -> None:
    pipeline = HierarchicalSummaryPipeline(settings, db)
    pipeline.run(doc_id=doc_id, source=source, run_id=run_id)
