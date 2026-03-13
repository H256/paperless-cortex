from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy.exc import SQLAlchemyError

from app.models import DocumentPageText, DocumentSuggestion
from app.services.runtime.json_utils import parse_json_object

if TYPE_CHECKING:
    import logging
    from collections.abc import Callable, Sequence

    from sqlalchemy.orm import Session

    from app.config import Settings


def variant_source_key(source: str, field: str) -> str:
    prefix = "pvar" if source == "paperless_ocr" else "vvar"
    return f"{prefix}:{field}"


def build_suggestions_meta(db: Session, doc_id: int) -> dict[str, dict[str, str | None]]:
    meta_rows = db.query(DocumentSuggestion).filter(DocumentSuggestion.doc_id == doc_id).all()
    ocr_model = (
        db.query(DocumentPageText.model_name)
        .filter(
            DocumentPageText.doc_id == doc_id,
            DocumentPageText.source == "vision_ocr",
        )
        .order_by(DocumentPageText.processed_at.desc().nullslast())
        .first()
    )
    ocr_model_name = ocr_model[0] if ocr_model else None
    return {
        row.source: {
            "model": row.model_name,
            "processed_at": row.processed_at,
            "ocr_model": ocr_model_name if row.source == "vision_ocr" else None,
        }
        for row in meta_rows
    }


def append_similar_docs_metadata(
    settings: Settings,
    db: Session,
    *,
    doc_id: int,
    suggestions_by_source: dict[str, object],
    logger: logging.Logger,
) -> None:
    try:
        from app.services.search.similarity import (
            aggregate_similar_metadata,
            fetch_doc_point_vector,
            search_similar_doc_points,
        )

        vector = fetch_doc_point_vector(settings, doc_id)
        if not vector:
            return
        matches = search_similar_doc_points(settings, vector, top_k=10, min_score=None)
        filtered = [item for item in matches if int(item["doc_id"]) != int(doc_id)]
        doc_ids = [int(item["doc_id"]) for item in filtered]
        score_by_doc = {int(item["doc_id"]): float(item.get("score") or 0.0) for item in filtered}
        metadata = aggregate_similar_metadata(db, doc_ids=doc_ids, score_by_doc=score_by_doc)
        suggestions_by_source["similar_docs"] = metadata
    except (ImportError, RuntimeError, SQLAlchemyError, ValueError, TypeError) as exc:
        logger.warning("Similar metadata failed doc=%s err=%s", doc_id, exc)


def get_document_suggestions_payload(
    *,
    doc_id: int,
    source: str | None,
    refresh: bool,
    priority: bool,
    include_similar: bool,
    settings: Settings,
    db: Session,
    logger: logging.Logger,
    get_document_fn: Callable[[Settings, int], dict[str, object]],
    get_cached_tags_fn: Callable[[Settings], list[str]],
    get_cached_correspondents_fn: Callable[[Settings], Sequence[object]],
    load_suggestions_map_fn: Callable[..., dict[str, object]],
    persist_suggestions_fn: Callable[..., None],
    generate_normalized_suggestions_fn: Callable[..., dict[str, object]],
    get_document_or_none_fn: Callable[[Session, int], object | None],
    collect_page_texts_fn: Callable[..., tuple[list[object], list[object], object]],
    enqueue_task_front_fn: Callable[[Settings, dict[str, object]], int],
    enqueue_task_sequence_front_fn: Callable[[Settings, list[dict[str, object]]], int],
) -> dict[str, object]:
    logger.info("Fetch suggestions doc=%s source=%s refresh=%s", doc_id, source, refresh)
    raw = get_document_fn(settings, doc_id)
    tags = get_cached_tags_fn(settings)
    correspondents = get_cached_correspondents_fn(settings)

    suggestions_by_source: dict[str, object] = {}

    def run_baseline() -> dict[str, object]:
        baseline_text = str(raw.get("content") or "")
        baseline_suggestions = generate_normalized_suggestions_fn(
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
        return baseline_suggestions

    def run_vision() -> dict[str, object] | None:
        if not settings.enable_vision_ocr:
            logger.warning("Vision OCR refresh requested but ENABLE_VISION_OCR=0 doc=%s", doc_id)
            return {"error": "vision_ocr_disabled"}
        doc = get_document_or_none_fn(db, doc_id)
        if not doc:
            return {"error": "document_missing"}
        _, vision_pages, _ = collect_page_texts_fn(
            settings,
            db,
            doc,
            force_vision=True,
        )
        if not vision_pages:
            logger.warning("Vision OCR produced no pages doc=%s", doc_id)
            return {"error": "vision_ocr_empty"}
        vision_text = "\n\n".join(getattr(page, "text", "") or "" for page in vision_pages).strip()
        if not vision_text:
            logger.warning("Vision OCR returned empty text doc=%s", doc_id)
            return {"error": "vision_ocr_empty_text"}
        vision_suggestions = generate_normalized_suggestions_fn(
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
        return vision_suggestions

    if refresh and priority and settings.queue_enabled:
        if source == "vision_ocr":
            enqueue_task_sequence_front_fn(
                settings,
                [
                    {"doc_id": doc_id, "task": "vision_ocr"},
                    {"doc_id": doc_id, "task": "embeddings_vision"},
                    {"doc_id": doc_id, "task": "suggestions_vision"},
                ],
            )
        elif source == "paperless_ocr":
            enqueue_task_front_fn(settings, {"doc_id": doc_id, "task": "suggestions_paperless"})
        suggestions_by_source = load_suggestions_map_fn(db, doc_id, tags)
        suggestions_meta = build_suggestions_meta(db, doc_id)
        if include_similar:
            append_similar_docs_metadata(
                settings,
                db,
                doc_id=doc_id,
                suggestions_by_source=suggestions_by_source,
                logger=logger,
            )
        return {
            "doc_id": doc_id,
            "queued": True,
            "suggestions": suggestions_by_source,
            "suggestions_meta": suggestions_meta,
        }

    if refresh:
        if source in (None, "paperless_ocr"):
            suggestions_by_source["paperless_ocr"] = run_baseline()
        if source in (None, "vision_ocr"):
            vision = run_vision()
            if vision is not None:
                suggestions_by_source["vision_ocr"] = vision
        if source == "vision_ocr" and "paperless_ocr" not in suggestions_by_source:
            suggestions_by_source.update(
                load_suggestions_map_fn(db, doc_id, tags, source="paperless_ocr")
            )
        if source == "paperless_ocr" and "vision_ocr" not in suggestions_by_source:
            suggestions_by_source.update(
                load_suggestions_map_fn(db, doc_id, tags, source="vision_ocr")
            )
    else:
        suggestions_by_source = load_suggestions_map_fn(db, doc_id, tags)

    suggestions_meta = build_suggestions_meta(db, doc_id)
    if include_similar:
        append_similar_docs_metadata(
            settings,
            db,
            doc_id=doc_id,
            suggestions_by_source=suggestions_by_source,
            logger=logger,
        )
    return {
        "doc_id": doc_id,
        "suggestions": suggestions_by_source,
        "suggestions_meta": suggestions_meta,
    }


def generate_field_variants_payload(
    *,
    doc_id: int,
    source: str,
    field: str,
    count: int,
    priority: bool,
    settings: Settings,
    db: Session,
    get_document_fn: Callable[[Settings, int], dict[str, object]],
    get_cached_tags_fn: Callable[[Settings], list[str]],
    get_cached_correspondents_fn: Callable[[Settings], Sequence[object]],
    get_document_or_none_fn: Callable[[Session, int], object | None],
    get_page_text_layers_fn: Callable[..., Any],
    fetch_pdf_bytes_fn: Callable[[], bytes],
    upsert_page_texts_fn: Callable[..., None],
    ensure_document_ocr_score_fn: Callable[..., object],
    generate_field_variants_fn: Callable[..., dict[str, object] | list[object]],
    enqueue_task_front_fn: Callable[[Settings, dict[str, object]], int],
) -> dict[str, object]:
    raw = get_document_fn(settings, doc_id)
    tags = get_cached_tags_fn(settings)
    correspondents = get_cached_correspondents_fn(settings)
    target_field = "summary" if field == "note" else field

    if source == "vision_ocr":
        vision_pages = (
            db.query(DocumentPageText)
            .filter(DocumentPageText.doc_id == doc_id, DocumentPageText.source == "vision_ocr")
            .order_by(DocumentPageText.page.asc())
            .all()
        )
        if not vision_pages and settings.enable_vision_ocr:
            _, vision_generated = get_page_text_layers_fn(
                settings,
                str(raw.get("content") or ""),
                fetch_pdf_bytes=fetch_pdf_bytes_fn,
                force_full_vision=True,
            )
            if vision_generated:
                upsert_page_texts_fn(db, settings, doc_id, vision_generated, source_filter="vision_ocr")
                doc = get_document_or_none_fn(db, doc_id)
                if doc:
                    ensure_document_ocr_score_fn(settings, db, doc, "vision_ocr", force=True)
                vision_pages = (
                    db.query(DocumentPageText)
                    .filter(
                        DocumentPageText.doc_id == doc_id,
                        DocumentPageText.source == "vision_ocr",
                    )
                    .order_by(DocumentPageText.page.asc())
                    .all()
                )
        text = "\n\n".join(page.text or "" for page in vision_pages) if vision_pages else ""
    else:
        text = str(raw.get("content") or "")

    current = None
    stored = (
        db.query(DocumentSuggestion)
        .filter(DocumentSuggestion.doc_id == doc_id, DocumentSuggestion.source == source)
        .one_or_none()
    )
    if stored:
        payload_json = parse_json_object(stored.payload)
        current = payload_json.get(target_field)
    if settings.queue_enabled and not priority:
        task = {
            "doc_id": doc_id,
            "task": "suggest_field",
            "source": source,
            "field": field,
            "count": max(1, min(count, 5)),
            "current": current,
        }
        enqueue_task_front_fn(settings, task)
        return {"doc_id": doc_id, "source": source, "field": field, "queued": True}

    generated = generate_field_variants_fn(
        settings,
        raw,
        text,
        tags=tags,
        correspondents=correspondents,
        field=field,
        count=max(1, min(count, 5)),
        current_value=current,
    )
    variants = generated.get("variants") if isinstance(generated, dict) else generated
    if not isinstance(variants, list):
        variants = []
    return {
        "doc_id": doc_id,
        "source": source,
        "field": field,
        "variants": variants,
    }


def format_ai_summary_note(
    summary_text: str,
    *,
    model_name: str | None,
    processed_at: str | None,
) -> str:
    def format_created(value: str | None) -> str | None:
        raw = str(value or "").strip()
        if not raw:
            return None
        candidate = f"{raw[:-1]}+00:00" if raw.endswith("Z") else raw
        try:
            parsed = datetime.fromisoformat(candidate)
            return parsed.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            compact = raw.replace("T", " ")
            return compact[:19]

    summary = summary_text.strip()
    meta_parts: list[str] = []
    if model_name:
        meta_parts.append(f"Model:{model_name}")
    created = format_created(processed_at)
    if created:
        meta_parts.append(f"Created:{created}")
    meta_line = ", ".join(meta_parts)
    if meta_line:
        return f"{summary}\n\n{meta_line}\nKI-Zusammenfassung"
    return f"{summary}\n\nKI-Zusammenfassung"
