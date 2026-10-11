from __future__ import annotations

import datetime
import logging
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from app.api_models import (
    ApplyFieldSuggestionResponse,
    ApplySuggestionResponse,
    SuggestFieldVariantsResponse,
    SuggestionsResponse,
    TextCandidatesResponse,
)
from app.db import get_db
from app.deps import get_settings
from app.exceptions import ValidationError
from app.models import DocumentPageText, DocumentSuggestion
from app.services.ai.correspondent_rules import learn_correspondent_rules
from app.services.ai.ocr_scoring import ensure_document_ocr_score
from app.services.ai.suggestion_apply import apply_suggestion_to_document_payload
from app.services.ai.suggestion_operations import (
    build_suggestions_meta,
    generate_field_variants_payload,
    get_document_suggestions_payload,
    variant_source_key,
)
from app.services.ai.suggestion_store import (
    audit_suggestion_run,
    load_suggestions_map,
    persist_suggestions,
    update_suggestion_field,
)
from app.services.ai.suggestion_warnings import compute_suggestion_warnings
from app.services.ai.suggestions import generate_field_variants, generate_normalized_suggestions
from app.services.ai.text_candidates import candidates_from_sources
from app.services.documents.documents import fetch_pdf_bytes, get_document_or_none
from app.services.documents.page_text_store import upsert_page_texts
from app.services.documents.page_texts_merge import collect_page_texts
from app.services.documents.text_pages import get_page_text_layers
from app.services.integrations import paperless
from app.services.integrations.meta_cache import get_cached_correspondents, get_cached_tags
from app.services.pipeline.queue import enqueue_task_front, enqueue_task_sequence_front
from app.services.pipeline.queue_access import is_queue_enabled
from app.services.runtime.json_utils import parse_json_object
from app.services.writeback.writeback_preview_cache import invalidate_writeback_preview_cache

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.config import Settings

require_queue_enabled = is_queue_enabled


def _attach_suggestion_warnings(payload: dict[str, object], settings: Settings) -> None:
    """Attach ``suggestion_warnings`` per source into the suggestions payload.

    Runs at read time against the freshest known-correspondent list and the
    current date, so the advisory hints never go stale. The ``similar_docs``
    source is non-actionable metadata (its ``correspondent`` is an aggregate
    of real docs, not a proposed value) and is skipped to avoid noise.
    """
    suggestions = payload.get("suggestions")
    if not isinstance(suggestions, dict):
        return
    known_correspondents = get_cached_correspondents(settings)
    reference_date = datetime.date.today()
    for source, value in suggestions.items():
        if source == "similar_docs" or not isinstance(value, dict):
            continue
        value["suggestion_warnings"] = compute_suggestion_warnings(
            value, known_correspondents, reference_date
        )

router = APIRouter(prefix="/documents", tags=["documents"])


class SuggestionFieldRequest(BaseModel):
    source: str
    field: str
    count: int = 3
    # Reviewer input for "Suggest new": a marked passage of the document text and a short hint.
    focus_text: str | None = None
    hint: str | None = None
    # OCR text the model reads (default: the text of `source`).
    text_source: str | None = None


class SuggestionFieldApply(BaseModel):
    source: str
    field: str
    value: object


def _variant_source_key(source: str, field: str) -> str:
    return variant_source_key(source, field)


def _build_suggestions_meta(db: Session, doc_id: int) -> dict[str, dict[str, str | None]]:
    return build_suggestions_meta(db, doc_id)


def _append_similar_docs_metadata(
    settings: Settings,
    db: Session,
    *,
    doc_id: int,
    suggestions_by_source: dict[str, object],
    logger: logging.Logger,
) -> None:
    try:
        from app.services.ai.suggestion_operations import append_similar_docs_metadata

        append_similar_docs_metadata(
            settings,
            db,
            doc_id=doc_id,
            suggestions_by_source=suggestions_by_source,
            logger=logger,
        )
    except (ImportError, RuntimeError, SQLAlchemyError, ValueError, TypeError) as exc:
        logger.warning("Similar metadata failed doc=%s err=%s", doc_id, exc)


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
    include_similar: bool = False,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    logger = logging.getLogger(__name__)
    payload = get_document_suggestions_payload(
        doc_id=doc_id,
        source=source,
        refresh=refresh,
        priority=priority,
        include_similar=include_similar,
        settings=settings,
        db=db,
        logger=logger,
        get_document_fn=paperless.get_document,
        get_cached_tags_fn=get_cached_tags,
        get_cached_correspondents_fn=get_cached_correspondents,
        load_suggestions_map_fn=load_suggestions_map,
        persist_suggestions_fn=persist_suggestions,
        generate_normalized_suggestions_fn=generate_normalized_suggestions,
        get_document_or_none_fn=get_document_or_none,
        collect_page_texts_fn=collect_page_texts,
        enqueue_task_front_fn=enqueue_task_front,
        enqueue_task_sequence_front_fn=enqueue_task_sequence_front,
        learn_rules_fn=learn_correspondent_rules,
    )
    _attach_suggestion_warnings(payload, settings)
    return payload


@router.get("/{doc_id}/suggestions/candidates", response_model=TextCandidatesResponse)
def get_text_candidates(
    doc_id: int,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """Deterministic date/correspondent candidates from the stored document text.

    Reads only cached page texts (fallback: document content); it never triggers OCR,
    LLM calls or queue work.
    """
    doc = get_document_or_none(db, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    rows = (
        db.query(DocumentPageText)
        .filter(DocumentPageText.doc_id == doc_id)
        .order_by(DocumentPageText.source.asc(), DocumentPageText.page.asc())
        .all()
    )
    sources: dict[str, list[tuple[int | None, str]]] = {}
    for row in rows:
        text = row.clean_text or row.text or row.raw_text or ""
        if text.strip():
            sources.setdefault(str(row.source), []).append((int(row.page), text))
    if not sources and (doc.content or "").strip():
        sources["content"] = [(None, str(doc.content))]
    known = get_cached_correspondents(settings)
    result = candidates_from_sources(sources, known)
    return {"doc_id": doc_id, **result}


@router.post("/{doc_id}/suggestions/field", response_model=SuggestFieldVariantsResponse)
def suggest_field_variants(
    doc_id: int,
    payload: SuggestionFieldRequest,
    priority: bool = False,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    if payload.source not in ("paperless_ocr", "vision_ocr"):
        raise ValidationError("Invalid source", field="source")
    if payload.field not in ("title", "date", "correspondent", "tags", "note"):
        raise ValidationError("Invalid field", field="field")
    payload_data = generate_field_variants_payload(
        doc_id=doc_id,
        source=payload.source,
        field=payload.field,
        count=payload.count,
        priority=priority,
        focus_text=payload.focus_text,
        hint=payload.hint,
        text_source=payload.text_source,
        settings=settings,
        db=db,
        get_document_fn=paperless.get_document,
        get_cached_tags_fn=get_cached_tags,
        get_cached_correspondents_fn=get_cached_correspondents,
        get_document_or_none_fn=get_document_or_none,
        get_page_text_layers_fn=get_page_text_layers,
        fetch_pdf_bytes_fn=lambda: fetch_pdf_bytes(settings, doc_id),
        upsert_page_texts_fn=upsert_page_texts,
        ensure_document_ocr_score_fn=ensure_document_ocr_score,
        generate_field_variants_fn=generate_field_variants,
        enqueue_task_front_fn=enqueue_task_front,
    )
    if payload_data.get("queued") is True:
        return payload_data
    audit_suggestion_run(db, doc_id, payload.source, f"field_variants:{payload.field}")
    return payload_data


@router.get("/{doc_id}/suggestions/field/variants", response_model=SuggestFieldVariantsResponse)
def get_field_variants(
    doc_id: int,
    source: str,
    field: str,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    variant_source = _variant_source_key(source, field)
    row = (
        db.query(DocumentSuggestion)
        .filter(DocumentSuggestion.doc_id == doc_id, DocumentSuggestion.source == variant_source)
        .one_or_none()
    )
    if not row:
        return {"doc_id": doc_id, "source": source, "field": field, "variants": []}
    payload_json = parse_json_object(row.payload)
    variants = payload_json.get("variants") or []
    return {"doc_id": doc_id, "source": source, "field": field, "variants": variants}


@router.post("/{doc_id}/suggestions/field/apply", response_model=ApplyFieldSuggestionResponse)
def apply_field_suggestion(
    doc_id: int,
    payload: SuggestionFieldApply,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if payload.source not in ("paperless_ocr", "vision_ocr"):
        raise ValidationError("Invalid source", field="source")
    if payload.field not in ("title", "date", "correspondent", "tags", "note"):
        raise ValidationError("Invalid field", field="field")
    target_field = "summary" if payload.field == "note" else payload.field
    updated = update_suggestion_field(db, doc_id, payload.source, target_field, payload.value)
    if updated is None:
        return {"status": "missing"}
    return {"status": "ok", "suggestions": {payload.source: updated}}


@router.post("/{doc_id}/apply-suggestion", response_model=ApplySuggestionResponse)
def apply_suggestion_to_document(
    doc_id: int,
    payload: ApplySuggestionToDocument,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    field = payload.field
    value = payload.value
    if field not in ("title", "date", "correspondent", "tags", "note"):
        raise ValidationError("Invalid field", field="field")
    result = apply_suggestion_to_document_payload(
        db=db,
        doc_id=doc_id,
        source=payload.source,
        field=field,
        value=value,
        get_document_or_none_fn=get_document_or_none,
        audit_suggestion_run_fn=audit_suggestion_run,
        invalidate_writeback_preview_cache_fn=invalidate_writeback_preview_cache,
    )
    if result.get("status") == "invalid_date":
        raise HTTPException(
            status_code=400,
            detail="document_date must be a valid ISO date in YYYY-MM-DD format",
        )
    return result
