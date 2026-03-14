from __future__ import annotations

import json
import logging
from json import JSONDecodeError
from typing import TYPE_CHECKING, Any

from app.models import DocumentPageNote, DocumentPageText, DocumentSuggestion
from app.services.ai.hierarchical_summary import is_large_document
from app.services.documents.documents import get_document_or_none
from app.services.documents.text_cleaning import clean_ocr_text

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    from sqlalchemy.orm import Session

    from app.config import Settings

logger = logging.getLogger(__name__)


def _page_text_value(page: object) -> str:
    clean_text = getattr(page, "clean_text", None)
    if isinstance(clean_text, str) and clean_text.strip():
        return clean_text
    raw_text = getattr(page, "text", None)
    if isinstance(raw_text, str):
        return clean_ocr_text(raw_text)
    return ""


def _normalized_variant_count(value: object, *, default: int = 3) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def join_page_texts_limited(pages: Iterable[object], max_chars: int) -> str:
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


def build_distilled_context_from_page_notes(
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
                    for key in (
                        "facts",
                        "entities",
                        "references",
                        "key_numbers",
                        "uncertainties",
                    ):
                        values = payload_obj.get(key)
                        if isinstance(values, list):
                            cleaned = [str(v).strip() for v in values if str(v).strip()]
                            if cleaned:
                                parts_list.append(f"{key}: " + "; ".join(cleaned[:12]))
                    text = "\n".join(parts_list).strip() or raw
        except JSONDecodeError:
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


def build_distilled_context_from_hier_summary(
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
    except JSONDecodeError:
        return ""
    if not isinstance(payload, dict):
        return ""
    payload_source = str(payload.get("source") or "").strip()
    if payload_source and payload_source != source:
        return ""

    summary = str(payload.get("summary") or "").strip()
    executive = str(payload.get("executive_summary") or "").strip()
    key_facts = payload.get("key_facts") if isinstance(payload.get("key_facts"), list) else []
    key_entities = (
        payload.get("key_entities") if isinstance(payload.get("key_entities"), list) else []
    )
    key_numbers = payload.get("key_numbers") if isinstance(payload.get("key_numbers"), list) else []
    key_dates = payload.get("key_dates") if isinstance(payload.get("key_dates"), list) else []
    has_signal = bool(summary or executive or key_facts or key_entities or key_numbers or key_dates)
    if not has_signal:
        notes_raw = payload.get("confidence_notes")
        notes_list = notes_raw if isinstance(notes_raw, list) else []
        note_text = " ".join(str(item).strip() for item in notes_list if str(item).strip()).lower()
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


def process_suggestions_paperless(
    settings: Settings,
    db: Session,
    doc_id: int,
    *,
    is_cancel_requested_fn: Callable[[Settings], bool],
    get_tags_fn: Callable[[Settings], Sequence[object]],
    get_correspondents_fn: Callable[[Settings], Sequence[object]],
    get_document_fn: Callable[[Settings, int], dict[str, Any]],
    generate_suggestions_fn: Callable[..., dict[str, Any]],
    persist_suggestions_fn: Callable[..., None],
) -> None:
    if is_cancel_requested_fn(settings):
        logger.info("Worker cancel requested; abort suggestions doc=%s", doc_id)
        return
    doc = get_document_or_none(db, doc_id)
    if not doc:
        return
    tags = get_tags_fn(settings)
    correspondents = get_correspondents_fn(settings)
    raw = get_document_fn(settings, doc_id)
    baseline_text = clean_ocr_text(doc.content or "")
    if is_large_document(
        page_count=doc.page_count,
        total_text=doc.content,
        threshold_pages=settings.large_doc_page_threshold,
    ):
        distilled = build_distilled_context_from_hier_summary(
            db,
            doc_id=doc_id,
            source="paperless_ocr",
            max_chars=settings.worker_suggestions_max_chars,
        )
        if not distilled:
            distilled = build_distilled_context_from_page_notes(
                db,
                doc_id=doc_id,
                source="paperless_ocr",
                max_chars=settings.worker_suggestions_max_chars,
            )
        if distilled:
            baseline_text = distilled
    baseline_suggestions = generate_suggestions_fn(
        settings,
        raw,
        baseline_text,
        tags=tags,
        correspondents=correspondents,
    )
    persist_suggestions_fn(
        db,
        doc_id,
        "paperless_ocr",
        baseline_suggestions,
        model_name=settings.text_model,
    )


def process_suggestions_vision(
    settings: Settings,
    db: Session,
    doc_id: int,
    *,
    is_cancel_requested_fn: Callable[[Settings], bool],
    get_tags_fn: Callable[[Settings], Sequence[object]],
    get_correspondents_fn: Callable[[Settings], Sequence[object]],
    get_document_fn: Callable[[Settings, int], dict[str, Any]],
    generate_suggestions_fn: Callable[..., dict[str, Any]],
    persist_suggestions_fn: Callable[..., None],
    process_vision_ocr_only_fn: Callable[..., None],
) -> None:
    if is_cancel_requested_fn(settings):
        logger.info("Worker cancel requested; abort vision suggestions doc=%s", doc_id)
        return
    tags = get_tags_fn(settings)
    correspondents = get_correspondents_fn(settings)
    raw = get_document_fn(settings, doc_id)
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
    has_complete_vision = (
        bool(vision_pages) if expected_pages <= 0 else len(bounded_pages) >= expected_pages
    )
    if settings.enable_vision_ocr and not has_complete_vision:
        logger.info(
            "Vision suggestions requested without complete vision OCR; backfilling doc=%s expected_pages=%s have=%s",
            doc_id,
            expected_pages if expected_pages > 0 else "unknown",
            len(bounded_pages),
        )
        process_vision_ocr_only_fn(settings, db, doc_id, force=False)
        vision_pages = (
            db.query(DocumentPageText)
            .filter(DocumentPageText.doc_id == doc_id, DocumentPageText.source == "vision_ocr")
            .order_by(DocumentPageText.page.asc())
            .all()
        )
    if not vision_pages:
        raise RuntimeError(f"vision_suggestions_missing_pages doc_id={doc_id}")

    vision_text = ""
    if is_large_document(
        page_count=doc.page_count,
        total_text=doc.content,
        threshold_pages=settings.large_doc_page_threshold,
    ):
        vision_text = build_distilled_context_from_hier_summary(
            db,
            doc_id=doc_id,
            source="vision_ocr",
            max_chars=settings.worker_suggestions_max_chars,
        )
    if not vision_text:
        vision_text = build_distilled_context_from_page_notes(
            db,
            doc_id=doc_id,
            source="vision_ocr",
            max_chars=settings.worker_suggestions_max_chars,
        )
    if not vision_text:
        vision_text = join_page_texts_limited(
            vision_pages,
            max_chars=settings.worker_suggestions_max_chars,
        )
    if not vision_text:
        raise RuntimeError(f"vision_suggestions_empty_text doc_id={doc_id}")

    vision_suggestions = generate_suggestions_fn(
        settings,
        raw,
        vision_text,
        tags=tags,
        correspondents=correspondents,
    )
    persist_suggestions_fn(
        db,
        doc_id,
        "vision_ocr",
        vision_suggestions,
        model_name=settings.text_model,
    )


def process_suggest_field(
    settings: Settings,
    db: Session,
    task: dict[str, object],
    *,
    get_document_fn: Callable[[Settings, int], dict[str, Any]],
    get_tags_fn: Callable[[Settings], Sequence[object]],
    get_correspondents_fn: Callable[[Settings], Sequence[object]],
    generate_field_variants_fn: Callable[..., dict[str, Any] | list[object]],
    upsert_suggestion_fn: Callable[..., None],
    audit_suggestion_run_fn: Callable[..., None],
) -> None:
    raw_doc_id = task.get("doc_id")
    if not isinstance(raw_doc_id, int):
        return
    doc_id = int(raw_doc_id)
    source = str(task.get("source") or "paperless_ocr")
    field = str(task.get("field") or "")
    count = _normalized_variant_count(task.get("count"))
    current = task.get("current")
    if source not in ("paperless_ocr", "vision_ocr") or field not in (
        "title",
        "date",
        "correspondent",
        "tags",
    ):
        return
    raw = get_document_fn(settings, doc_id)
    tags = get_tags_fn(settings)
    correspondents = get_correspondents_fn(settings)
    if source == "vision_ocr":
        vision_pages = (
            db.query(DocumentPageText)
            .filter(DocumentPageText.doc_id == doc_id, DocumentPageText.source == "vision_ocr")
            .order_by(DocumentPageText.page.asc())
            .all()
        )
        text = join_page_texts_limited(vision_pages, max_chars=settings.worker_suggestions_max_chars)
    else:
        doc = get_document_or_none(db, doc_id)
        text = clean_ocr_text(doc.content) if doc and doc.content else ""
    variants = generate_field_variants_fn(
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
    upsert_suggestion_fn(
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
    audit_suggestion_run_fn(db, doc_id, source, f"field_variants:{field}", commit=False)
    db.commit()
