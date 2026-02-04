from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import get_db
from app.deps import get_settings
from app.models import (
    Correspondent,
    Document,
    DocumentNote,
    DocumentPageText,
    DocumentSuggestion,
    Tag,
)
from app.services import paperless
from app.services.meta_cache import get_cached_correspondents, get_cached_tags
from app.services.page_text_store import upsert_page_texts
from app.services.documents import fetch_pdf_bytes, get_document_or_none
from app.services.page_texts_merge import collect_page_texts
from app.services.queue import enqueue_task_front, enqueue_task_sequence_front
from app.services.suggestion_store import audit_suggestion_run, persist_suggestions, update_suggestion_field
from app.services.suggestions import generate_field_variants, generate_normalized_suggestions, merge_suggestions
from app.services.text_pages import get_page_text_layers
from app.api_models import (
    ApplyFieldSuggestionResponse,
    ApplySuggestionResponse,
    SuggestFieldVariantsResponse,
    SuggestionsResponse,
)
from app.routes.documents_common import load_suggestions_map
from app.routes.queue_guard import require_queue_enabled

router = APIRouter(prefix="/documents", tags=["documents"])


class SuggestionFieldRequest(BaseModel):
    source: str
    field: str
    count: int = 3


class SuggestionFieldApply(BaseModel):
    source: str
    field: str
    value: object


def _variant_source_key(source: str, field: str) -> str:
    prefix = "pvar" if source == "paperless_ocr" else "vvar"
    return f"{prefix}:{field}"


class ApplySuggestionToDocument(BaseModel):
    source: str | None = None
    field: str
    value: object


@router.get("/{doc_id}/suggestions", response_model=SuggestionsResponse)
def get_document_suggestions(
    doc_id: int,
    source: str | None = None,
    refresh: bool = False,
    priority: bool = False,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    logger = __import__("logging").getLogger(__name__)
    logger.info("Fetch suggestions doc=%s source=%s refresh=%s", doc_id, source, refresh)
    raw = paperless.get_document(settings, doc_id)
    tags = get_cached_tags(settings)
    correspondents = get_cached_correspondents(settings)

    suggestions_by_source: dict[str, object] = {}

    def run_baseline() -> dict[str, object]:
        baseline_text = raw.get("content") or ""
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
            model_name=settings.ollama_model,
        )
        return baseline_suggestions

    def run_vision() -> dict[str, object] | None:
        if not settings.enable_vision_ocr:
            logger.warning("Vision OCR refresh requested but ENABLE_VISION_OCR=0 doc=%s", doc_id)
            return {"error": "vision_ocr_disabled"}
        doc = get_document_or_none(db, doc_id)
        if not doc:
            return {"error": "document_missing"}
        _, vision_pages, _ = collect_page_texts(
            settings,
            db,
            doc,
            force_vision=True,
        )
        if not vision_pages:
            logger.warning("Vision OCR produced no pages doc=%s", doc_id)
            return {"error": "vision_ocr_empty"}
        vision_text = "\n\n".join(page.text or "" for page in vision_pages).strip()
        if not vision_text:
            logger.warning("Vision OCR returned empty text doc=%s", doc_id)
            return {"error": "vision_ocr_empty_text"}
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
            model_name=settings.ollama_model,
        )
        return vision_suggestions

    if refresh and priority and require_queue_enabled(settings):
        if source == "vision_ocr":
            enqueue_task_sequence_front(
                settings,
                [
                    {"doc_id": doc_id, "task": "vision_ocr"},
                    {"doc_id": doc_id, "task": "embeddings_vision"},
                    {"doc_id": doc_id, "task": "suggestions_vision"},
                ],
            )
        elif source == "paperless_ocr":
            enqueue_task_front(settings, {"doc_id": doc_id, "task": "suggestions_paperless"})
        suggestions_by_source = load_suggestions_map(db, doc_id, tags)
        meta_rows = (
            db.query(DocumentSuggestion)
            .filter(DocumentSuggestion.doc_id == doc_id)
            .all()
        )
        suggestions_meta = {
            row.source: {"model": row.model_name, "processed_at": row.processed_at}
            for row in meta_rows
        }
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
            suggestions_by_source.update(load_suggestions_map(db, doc_id, tags, source="paperless_ocr"))
        if source == "paperless_ocr" and "vision_ocr" not in suggestions_by_source:
            suggestions_by_source.update(load_suggestions_map(db, doc_id, tags, source="vision_ocr"))
    else:
        suggestions_by_source = load_suggestions_map(db, doc_id, tags)

    meta_rows = (
        db.query(DocumentSuggestion)
        .filter(DocumentSuggestion.doc_id == doc_id)
        .all()
    )
    suggestions_meta = {
        row.source: {"model": row.model_name, "processed_at": row.processed_at}
        for row in meta_rows
    }
    best = merge_suggestions(
        suggestions_by_source.get("paperless_ocr"),
        suggestions_by_source.get("vision_ocr"),
    )
    if best:
        suggestions_by_source["best_pick"] = best
    return {
        "doc_id": doc_id,
        "suggestions": suggestions_by_source,
        "suggestions_meta": suggestions_meta,
    }


@router.post("/{doc_id}/suggestions/field", response_model=SuggestFieldVariantsResponse)
def suggest_field_variants(
    doc_id: int,
    payload: SuggestionFieldRequest,
    priority: bool = False,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    raw = paperless.get_document(settings, doc_id)
    tags = get_cached_tags(settings)
    correspondents = get_cached_correspondents(settings)
    if payload.source not in ("paperless_ocr", "vision_ocr"):
        raise ValueError("Invalid source")
    if payload.field not in ("title", "date", "correspondent", "tags"):
        raise ValueError("Invalid field")

    if payload.source == "vision_ocr":
        vision_pages = (
            db.query(DocumentPageText)
            .filter(DocumentPageText.doc_id == doc_id, DocumentPageText.source == "vision_ocr")
            .order_by(DocumentPageText.page.asc())
            .all()
        )
        if not vision_pages and settings.enable_vision_ocr:
            _, vision_generated = get_page_text_layers(
                settings,
                raw.get("content") or "",
                fetch_pdf_bytes=lambda: fetch_pdf_bytes(settings, doc_id),
                force_full_vision=True,
            )
            if vision_generated:
                upsert_page_texts(db, settings, doc_id, vision_generated, source_filter="vision_ocr")
                vision_pages = (
                    db.query(DocumentPageText)
                    .filter(DocumentPageText.doc_id == doc_id, DocumentPageText.source == "vision_ocr")
                    .order_by(DocumentPageText.page.asc())
                    .all()
                )
        text = "\n\n".join(page.text or "" for page in vision_pages) if vision_pages else ""
    else:
        text = raw.get("content") or ""

    current = None
    stored = (
        db.query(DocumentSuggestion)
        .filter(DocumentSuggestion.doc_id == doc_id, DocumentSuggestion.source == payload.source)
        .one_or_none()
    )
    if stored:
        try:
            payload_json = json.loads(stored.payload)
        except Exception:
            payload_json = {}
        if isinstance(payload_json, dict):
            current = payload_json.get(payload.field)
    if require_queue_enabled(settings):
        task = {
            "doc_id": doc_id,
            "task": "suggest_field",
            "source": payload.source,
            "field": payload.field,
            "count": max(1, min(payload.count, 5)),
            "current": current,
        }
        enqueue_task_front(settings, task)
        return {"doc_id": doc_id, "source": payload.source, "field": payload.field, "queued": True}

    variants = generate_field_variants(
        settings,
        raw,
        text,
        tags=tags,
        correspondents=correspondents,
        field=payload.field,
        count=max(1, min(payload.count, 5)),
        current_value=current,
    )
    audit_suggestion_run(db, doc_id, payload.source, f"field_variants:{payload.field}")
    return {"doc_id": doc_id, "source": payload.source, "field": payload.field, "variants": variants}


@router.get("/{doc_id}/suggestions/field/variants", response_model=SuggestFieldVariantsResponse)
def get_field_variants(
    doc_id: int,
    source: str,
    field: str,
    db: Session = Depends(get_db),
):
    variant_source = _variant_source_key(source, field)
    row = (
        db.query(DocumentSuggestion)
        .filter(DocumentSuggestion.doc_id == doc_id, DocumentSuggestion.source == variant_source)
        .one_or_none()
    )
    if not row:
        return {"doc_id": doc_id, "source": source, "field": field, "variants": []}
    try:
        payload_json = json.loads(row.payload)
    except Exception:
        payload_json = {}
    variants = payload_json.get("variants") or []
    return {"doc_id": doc_id, "source": source, "field": field, "variants": variants}


@router.post("/{doc_id}/suggestions/field/apply", response_model=ApplyFieldSuggestionResponse)
def apply_field_suggestion(
    doc_id: int,
    payload: SuggestionFieldApply,
    db: Session = Depends(get_db),
):
    if payload.source not in ("paperless_ocr", "vision_ocr"):
        raise ValueError("Invalid source")
    if payload.field not in ("title", "date", "correspondent", "tags"):
        raise ValueError("Invalid field")
    updated = update_suggestion_field(db, doc_id, payload.source, payload.field, payload.value)
    if updated is None:
        return {"status": "missing"}
    return {"status": "ok", "suggestions": {payload.source: updated}}


@router.post("/{doc_id}/apply-suggestion", response_model=ApplySuggestionResponse)
def apply_suggestion_to_document(
    doc_id: int,
    payload: ApplySuggestionToDocument,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    logger = __import__("logging").getLogger(__name__)
    doc = get_document_or_none(db, doc_id)
    if not doc:
        return {"status": "missing"}
    field = payload.field
    value = payload.value
    if field not in ("title", "date", "correspondent", "tags", "note"):
        raise ValueError("Invalid field")
    old_value = None
    updated = False
    details: dict[str, object] = {}

    if field == "title":
        old_value = doc.title
        doc.title = str(value).strip() if value is not None else None
        updated = True
    elif field == "date":
        old_value = doc.document_date
        doc.document_date = str(value).strip() if value is not None else None
        updated = True
    elif field == "correspondent":
        old_value = doc.correspondent_id
        name = str(value).strip() if value is not None else ""
        if name:
            like_term = f"%{name}%"
            match = (
                db.query(Correspondent)
                .filter(Correspondent.name.ilike(like_term))
                .order_by(
                    case((Correspondent.name.ilike(name), 0), else_=1),
                    func.length(Correspondent.name).asc(),
                )
                .first()
            )
            if match:
                doc.correspondent_id = match.id
                updated = True
            else:
                details["unmatched"] = name
        else:
            doc.correspondent_id = None
            updated = True
    elif field == "tags":
        old_value = [tag.name for tag in doc.tags]
        tag_names: list[str] = []
        if isinstance(value, list):
            tag_names = [str(v).strip() for v in value if str(v).strip()]
        elif isinstance(value, str):
            tag_names = [v.strip() for v in value.split(",") if v.strip()]
        matched: list[Tag] = []
        unmatched: list[str] = []
        for name in tag_names:
            row = db.query(Tag).filter(Tag.name.ilike(name)).one_or_none()
            if row:
                matched.append(row)
            else:
                unmatched.append(name)
        if matched:
            doc.tags = matched
            updated = True
        details["unmatched"] = unmatched
    elif field == "note":
        summary = str(value).strip() if value is not None else ""
        if summary:
            marker_text = f"AI_SUMMARY v1 –\n{summary}\n- /AI_SUMMARY -"
            existing_note = (
                db.query(DocumentNote)
                .filter(DocumentNote.document_id == doc_id, DocumentNote.note.like("AI_SUMMARY v1 –%"))
                .order_by(DocumentNote.id.asc())
                .first()
            )
            if existing_note:
                old_value = existing_note.note
                existing_note.note = marker_text
                existing_note.created = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
                updated = True
            else:
                max_id = db.query(func.max(DocumentNote.id)).scalar() or 0
                note = DocumentNote(
                    id=int(max_id) + 1,
                    document_id=doc_id,
                    note=marker_text,
                    created=__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
                )
                db.add(note)
                updated = True

    if updated:
        audit_suggestion_run(db, doc_id, payload.source or "manual", f"apply_to_document:{field}")
        db.commit()
        logger.info("Applied suggestion to document doc=%s field=%s", doc_id, field)
        return {"status": "ok", "updated": True, **details}
    return {"status": "skipped", "updated": False, **details}
