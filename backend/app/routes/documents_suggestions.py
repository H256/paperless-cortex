from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from app.api_models import (
    ApplyFieldSuggestionResponse,
    ApplySuggestionResponse,
    SuggestFieldVariantsResponse,
    SuggestionsResponse,
)
from app.db import get_db
from app.deps import get_settings
from app.models import DocumentSuggestion
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
from app.services.ai.suggestions import generate_field_variants, generate_normalized_suggestions
from app.services.documents.documents import fetch_pdf_bytes, get_document_or_none
from app.services.documents.page_text_store import upsert_page_texts
from app.services.documents.page_texts_merge import collect_page_texts
from app.services.documents.text_pages import get_page_text_layers
from app.services.integrations import paperless
from app.services.integrations.meta_cache import get_cached_correspondents, get_cached_tags
from app.services.pipeline.queue import enqueue_task_front, enqueue_task_sequence_front
from app.services.pipeline.queue_access import is_queue_enabled
from app.services.runtime.json_utils import parse_json_object

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.config import Settings

require_queue_enabled = is_queue_enabled

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
    return get_document_suggestions_payload(
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
    )


@router.post("/{doc_id}/suggestions/field", response_model=SuggestFieldVariantsResponse)
def suggest_field_variants(
    doc_id: int,
    payload: SuggestionFieldRequest,
    priority: bool = False,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    if payload.source not in ("paperless_ocr", "vision_ocr"):
        raise ValueError("Invalid source")
    if payload.field not in ("title", "date", "correspondent", "tags", "note"):
        raise ValueError("Invalid field")
    payload_data = generate_field_variants_payload(
        doc_id=doc_id,
        source=payload.source,
        field=payload.field,
        count=payload.count,
        priority=priority,
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
        raise ValueError("Invalid source")
    if payload.field not in ("title", "date", "correspondent", "tags", "note"):
        raise ValueError("Invalid field")
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
        raise ValueError("Invalid field")
    return apply_suggestion_to_document_payload(
        db=db,
        doc_id=doc_id,
        source=payload.source,
        field=field,
        value=value,
        get_document_or_none_fn=get_document_or_none,
        audit_suggestion_run_fn=audit_suggestion_run,
    )
