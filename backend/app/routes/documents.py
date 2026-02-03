from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import and_, exists, func
from sqlalchemy.orm import Session
from time import time

from app.config import Settings, load_settings
from app.db import get_db
import json

from pydantic import BaseModel

from app.models import (
    Document,
    DocumentPageText,
    DocumentSuggestion,
    DocumentEmbedding,
    Tag,
    Correspondent,
    DocumentType,
    DocumentNote,
    SuggestionAudit,
    document_tags,
)
from app.services.meta_cache import get_cached_correspondents, get_cached_tags
from app.services.suggestions import (
    generate_suggestions,
    generate_field_variants,
    normalize_suggestions_payload,
    merge_suggestions,
)
from app.services import paperless
from app.services.text_pages import get_baseline_page_texts, get_page_text_layers, score_text_quality
from app.services.suggestion_store import upsert_suggestion, audit_suggestion_run
from app.services.suggestion_store import update_suggestion_field
from app.services.page_text_store import upsert_page_texts
from app.services.queue import enqueue_docs_front, enqueue_task_front, enqueue_task_sequence_front
from app.services.vision_ocr import render_pdf_pages
from app.services.embeddings import delete_points_for_doc
from app.api_models import (
    ApplyFieldSuggestionResponse,
    ApplySuggestionResponse,
    DocumentLocalResponse,
    DocumentStatsResponse,
    DocumentDashboardResponse,
    DocumentSummary,
    DocumentsPageResponse,
    DocumentTextQualityResponse,
    PageTextsResponse,
    PaperlessDocument,
    SuggestFieldVariantsResponse,
    SuggestionsResponse,
    ProcessMissingResponse,
    ResetIntelligenceResponse,
    ClearIntelligenceResponse,
    DeleteEmbeddingsResponse,
    DeleteSuggestionsResponse,
    DeleteVisionOcrResponse,
)
from app.services.queue import enqueue_task_sequence
from sqlalchemy import delete
from datetime import datetime

router = APIRouter(prefix="/documents", tags=["documents"])
_preview_cache: dict[tuple[int, int, int], tuple[float, bytes]] = {}
_preview_cache_ttl = 600.0


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _should_skip_doc(doc: Document) -> bool:
    return bool(doc.deleted_at and str(doc.deleted_at).startswith("DELETED in Paperless"))


def settings_dep() -> Settings:
    return load_settings()


@router.get("/", response_model=DocumentsPageResponse)
def list_documents(
    page: int = 1,
    page_size: int = 20,
    ordering: str | None = None,
    correspondent__id: int | None = None,
    tags__id: int | None = None,
    document_date__gte: str | None = None,
    document_date__lte: str | None = None,
    include_derived: bool = False,
    settings: Settings = Depends(settings_dep),
    db: Session = Depends(get_db),
):
    payload = paperless.list_documents(
        settings,
        page=page,
        page_size=page_size,
        ordering=ordering,
        correspondent__id=correspondent__id,
        tags__id=tags__id,
        document_date__gte=document_date__gte,
        document_date__lte=document_date__lte,
    )
    if not include_derived:
        return payload
    results = payload.get("results", []) or []
    doc_ids = [doc.get("id") for doc in results if doc.get("id") is not None]
    if not doc_ids:
        return payload
    analysis_by_doc = {
        row.id: {
            "analysis_model": row.analysis_model,
            "analysis_processed_at": row.analysis_processed_at,
        }
        for row in db.query(Document.id, Document.analysis_model, Document.analysis_processed_at)
        .filter(Document.id.in_(doc_ids))
        .all()
    }
    local_docs = (
        db.query(Document)
        .filter(Document.id.in_(doc_ids))
        .all()
    )
    local_by_id = {doc.id: doc for doc in local_docs}
    embed_ids = {row.doc_id for row in db.query(DocumentEmbedding).filter(DocumentEmbedding.doc_id.in_(doc_ids)).all()}
    suggestion_rows = (
        db.query(DocumentSuggestion)
        .filter(DocumentSuggestion.doc_id.in_(doc_ids))
        .all()
    )
    suggestions_by_doc: dict[int, set[str]] = {}
    for row in suggestion_rows:
        suggestions_by_doc.setdefault(row.doc_id, set()).add(row.source)
    vision_pages = {
        row.doc_id
        for row in db.query(DocumentPageText)
        .filter(DocumentPageText.doc_id.in_(doc_ids), DocumentPageText.source == "vision_ocr")
        .all()
    }
    for doc in results:
        doc_id = doc.get("id")
        if doc_id is None:
            continue
        local_doc = local_by_id.get(doc_id)
        doc["local_cached"] = local_doc is not None
        local_overrides = False
        if local_doc:
            local_tags = [tag.id for tag in local_doc.tags]
            paperless_tags = doc.get("tags") or []
            if set(local_tags) != set(paperless_tags):
                local_overrides = True
            if local_doc.title and local_doc.title != doc.get("title"):
                local_overrides = True
            if local_doc.document_date and local_doc.document_date != doc.get("document_date"):
                local_overrides = True
            if local_doc.correspondent_id and local_doc.correspondent_id != doc.get("correspondent"):
                local_overrides = True
            if local_overrides:
                doc["title"] = local_doc.title
                doc["document_date"] = local_doc.document_date
                doc["correspondent"] = local_doc.correspondent_id
                doc["correspondent_name"] = local_doc.correspondent.name if local_doc.correspondent else None
                doc["tags"] = local_tags
        doc["local_overrides"] = local_overrides
        doc["has_embeddings"] = doc_id in embed_ids
        doc.update(analysis_by_doc.get(doc_id, {}))
        sources = suggestions_by_doc.get(doc_id, set())
        doc["has_suggestions"] = bool(sources)
        doc["has_suggestions_paperless"] = "paperless_ocr" in sources
        doc["has_suggestions_vision"] = "vision_ocr" in sources
        doc["has_vision_pages"] = doc_id in vision_pages
    return payload


@router.get("/stats", response_model=DocumentStatsResponse)
def get_document_stats(db: Session = Depends(get_db)):
    total = db.query(Document).count()
    embeddings = (
        db.query(Document.id)
        .filter(exists().where(DocumentEmbedding.doc_id == Document.id))
        .count()
    )
    vision = (
        db.query(Document.id)
        .filter(
            exists().where(
                and_(
                    DocumentPageText.doc_id == Document.id,
                    DocumentPageText.source == "vision_ocr",
                )
            )
        )
        .count()
    )
    suggestions = (
        db.query(Document.id)
        .filter(exists().where(DocumentSuggestion.doc_id == Document.id))
        .count()
    )
    fully_processed = (
        db.query(Document.id)
        .filter(
            exists().where(DocumentEmbedding.doc_id == Document.id),
            exists().where(
                and_(
                    DocumentPageText.doc_id == Document.id,
                    DocumentPageText.source == "vision_ocr",
                )
            ),
            exists().where(DocumentSuggestion.doc_id == Document.id),
        )
        .count()
    )
    unprocessed = max(0, total - fully_processed)
    return {
        "total": total,
        "processed": embeddings,
        "unprocessed": unprocessed,
        "embeddings": embeddings,
        "vision": vision,
        "suggestions": suggestions,
        "fully_processed": fully_processed,
    }


@router.get("/dashboard", response_model=DocumentDashboardResponse)
def get_dashboard(db: Session = Depends(get_db)):
    stats = get_document_stats(db)
    fully_processed_ids = {
        row[0]
        for row in db.query(Document.id)
        .filter(
            exists().where(DocumentEmbedding.doc_id == Document.id),
            exists().where(
                and_(
                    DocumentPageText.doc_id == Document.id,
                    DocumentPageText.source == "vision_ocr",
                )
            ),
            exists().where(DocumentSuggestion.doc_id == Document.id),
        )
        .all()
    }

    correspondents_rows = (
        db.query(Correspondent.id, Correspondent.name, func.count(Document.id))
        .join(Document, Document.correspondent_id == Correspondent.id)
        .group_by(Correspondent.id)
        .order_by(func.count(Document.id).desc(), Correspondent.name.asc())
        .all()
    )
    unassigned_count = db.query(Document.id).filter(Document.correspondent_id.is_(None)).count()
    correspondents = [
        {"id": row[0], "name": row[1] or "Unbenannt", "count": row[2]}
        for row in correspondents_rows
    ]
    if unassigned_count:
        correspondents.append({"id": None, "name": "Ohne Korrespondent", "count": unassigned_count})
    correspondents.sort(key=lambda item: item["count"], reverse=True)
    top_correspondents = correspondents[:8]

    tag_rows = (
        db.query(Tag.id, Tag.name, func.count(document_tags.c.document_id))
        .join(document_tags, Tag.id == document_tags.c.tag_id)
        .group_by(Tag.id)
        .order_by(func.count(document_tags.c.document_id).desc(), Tag.name.asc())
        .all()
    )
    untagged_count = (
        db.query(Document.id)
        .filter(~exists().where(document_tags.c.document_id == Document.id))
        .count()
    )
    tags = [{"id": row[0], "name": row[1] or "Unbenannt", "count": row[2]} for row in tag_rows]
    if untagged_count:
        tags.append({"id": None, "name": "Ohne Tags", "count": untagged_count})
    tags.sort(key=lambda item: item["count"], reverse=True)
    top_tags = tags[:8]

    type_rows = (
        db.query(DocumentType.id, DocumentType.name, func.count(Document.id))
        .join(Document, Document.document_type_id == DocumentType.id)
        .group_by(DocumentType.id)
        .order_by(func.count(Document.id).desc(), DocumentType.name.asc())
        .all()
    )
    type_unknown = db.query(Document.id).filter(Document.document_type_id.is_(None)).count()
    document_types = [
        {"id": row[0], "name": row[1] or "Unbenannt", "count": row[2]}
        for row in type_rows
    ]
    if type_unknown:
        document_types.append({"id": None, "name": "Ohne Typ", "count": type_unknown})
    document_types.sort(key=lambda item: item["count"], reverse=True)

    unprocessed_by_correspondent: dict[int | None, int] = {}
    monthly: dict[str, dict[str, int]] = {}
    for doc_id, document_date, created, correspondent_id in db.query(
        Document.id,
        Document.document_date,
        Document.created,
        Document.correspondent_id,
    ).all():
        processed = doc_id in fully_processed_ids
        if not processed:
            unprocessed_by_correspondent[correspondent_id] = unprocessed_by_correspondent.get(correspondent_id, 0) + 1

        raw_date = document_date or created or ""
        month = raw_date[:7] if len(raw_date) >= 7 else "Unbekannt"
        bucket = monthly.get(month)
        if bucket is None:
            bucket = {"total": 0, "processed": 0, "unprocessed": 0}
            monthly[month] = bucket
        bucket["total"] += 1
        if processed:
            bucket["processed"] += 1
        else:
            bucket["unprocessed"] += 1

    correspondents_map = {row[0]: row[1] for row in db.query(Correspondent.id, Correspondent.name).all()}
    unprocessed_corr_list = [
        {
            "id": corr_id,
            "name": correspondents_map.get(corr_id) or ("Ohne Korrespondent" if corr_id is None else "Unbenannt"),
            "count": count,
        }
        for corr_id, count in unprocessed_by_correspondent.items()
    ]
    unprocessed_corr_list.sort(key=lambda item: item["count"], reverse=True)

    monthly_processing = [
        {"label": month, **counts} for month, counts in sorted(monthly.items(), key=lambda item: item[0])
    ]
    if monthly_processing and monthly_processing[0]["label"] == "Unbekannt":
        monthly_processing = monthly_processing[1:] + [monthly_processing[0]]

    buckets = {
        "1": 0,
        "2-3": 0,
        "4-6": 0,
        "7-10": 0,
        "11-20": 0,
        "21-50": 0,
        "51+": 0,
        "Unbekannt": 0,
    }
    for (page_count,) in db.query(Document.page_count).all():
        if page_count is None or page_count < 1:
            buckets["Unbekannt"] += 1
        elif page_count == 1:
            buckets["1"] += 1
        elif page_count <= 3:
            buckets["2-3"] += 1
        elif page_count <= 6:
            buckets["4-6"] += 1
        elif page_count <= 10:
            buckets["7-10"] += 1
        elif page_count <= 20:
            buckets["11-20"] += 1
        elif page_count <= 50:
            buckets["21-50"] += 1
        else:
            buckets["51+"] += 1

    page_counts = [{"label": label, "count": count} for label, count in buckets.items()]

    return {
        "stats": stats,
        "correspondents": correspondents,
        "top_correspondents": top_correspondents,
        "tags": tags,
        "top_tags": top_tags,
        "page_counts": page_counts,
        "document_types": document_types,
        "unprocessed_by_correspondent": unprocessed_corr_list,
        "monthly_processing": monthly_processing,
    }


@router.get("/{doc_id}", response_model=PaperlessDocument)
def get_document(doc_id: int, settings: Settings = Depends(settings_dep)):
    return paperless.get_document(settings, doc_id)


@router.get("/{doc_id}/local", response_model=DocumentLocalResponse)
def get_local_document(doc_id: int, db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if not doc:
        return {"status": "missing"}
    return {
        "id": doc.id,
        "title": doc.title,
        "content": doc.content,
        "document_date": doc.document_date,
        "created": doc.created,
        "modified": doc.modified,
        "correspondent": doc.correspondent_id,
        "correspondent_name": doc.correspondent.name if doc.correspondent else None,
        "document_type": doc.document_type_id,
        "document_type_name": doc.document_type.name if doc.document_type else None,
        "tags": [tag.id for tag in doc.tags],
        "notes": [{"note": note.note} for note in doc.notes],
        "original_file_name": doc.original_file_name,
    }


@router.get("/{doc_id}/text-quality", response_model=DocumentTextQualityResponse)
def get_document_text_quality(
    doc_id: int,
    priority: bool = False,
    settings: Settings = Depends(settings_dep),
):
    logger = __import__("logging").getLogger(__name__)
    logger.info("Fetch text quality doc=%s", doc_id)
    if priority and settings.queue_enabled:
        enqueue_docs_front(settings, [doc_id])
    raw = paperless.get_document(settings, doc_id)
    content = raw.get("content") or ""
    quality = score_text_quality(content, settings)
    logger.info(
        "Text quality doc=%s score=%s reasons=%s",
        doc_id,
        quality.score,
        quality.reasons,
    )
    return {
        "doc_id": doc_id,
        "quality": {
            "score": quality.score,
            "reasons": quality.reasons,
            "metrics": quality.metrics,
        },
    }


@router.get("/{doc_id}/suggestions", response_model=SuggestionsResponse)
def get_document_suggestions(
    doc_id: int,
    source: str | None = None,
    refresh: bool = False,
    priority: bool = False,
    settings: Settings = Depends(settings_dep),
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
        baseline_suggestions = generate_suggestions(
            settings,
            raw,
            baseline_text,
            tags=tags,
            correspondents=correspondents,
        )
        baseline_suggestions = normalize_suggestions_payload(baseline_suggestions, tags)
        upsert_suggestion(
            db,
            doc_id,
            "paperless_ocr",
            json.dumps(baseline_suggestions, ensure_ascii=False),
            model_name=settings.ollama_model,
        )
        audit_suggestion_run(db, doc_id, "paperless_ocr", "suggestions_generate")
        return baseline_suggestions

    def run_vision() -> dict[str, object] | None:
        vision_pages = (
            db.query(DocumentPageText)
            .filter(DocumentPageText.doc_id == doc_id, DocumentPageText.source == "vision_ocr")
            .order_by(DocumentPageText.page.asc())
            .all()
        )
        if not vision_pages:
            if not settings.enable_vision_ocr:
                logger.warning("Vision OCR refresh requested but ENABLE_VISION_OCR=0 doc=%s", doc_id)
                return {"error": "vision_ocr_disabled"}
            logger.info("Vision OCR pages missing; running OCR on-demand doc=%s", doc_id)
            _, vision_generated = get_page_text_layers(
                settings,
                raw.get("content") or "",
                fetch_pdf_bytes=lambda: paperless.get_document_pdf(settings, doc_id),
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
        if not vision_pages:
            logger.warning("Vision OCR produced no pages doc=%s", doc_id)
            return {"error": "vision_ocr_empty"}
        vision_text = "\n\n".join(page.text or "" for page in vision_pages).strip()
        if not vision_text:
            logger.warning("Vision OCR returned empty text doc=%s", doc_id)
            return {"error": "vision_ocr_empty_text"}
        vision_suggestions = generate_suggestions(
            settings,
            raw,
            vision_text,
            tags=tags,
            correspondents=correspondents,
        )
        vision_suggestions = normalize_suggestions_payload(vision_suggestions, tags)
        upsert_suggestion(
            db,
            doc_id,
            "vision_ocr",
            json.dumps(vision_suggestions, ensure_ascii=False),
            model_name=settings.ollama_model,
        )
        audit_suggestion_run(db, doc_id, "vision_ocr", "suggestions_generate")
        return vision_suggestions

    if refresh and priority and settings.queue_enabled:
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
        stored = (
            db.query(DocumentSuggestion)
            .filter(DocumentSuggestion.doc_id == doc_id)
            .order_by(DocumentSuggestion.source.asc())
            .all()
        )
        for row in stored:
            try:
                parsed = json.loads(row.payload)
                suggestions_by_source[row.source] = normalize_suggestions_payload(parsed, tags)
            except Exception:
                suggestions_by_source[row.source] = {"raw": row.payload}
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
        # Ensure best_pick has both sources when refreshing only one side.
        if source == "vision_ocr" and "paperless_ocr" not in suggestions_by_source:
            stored = (
                db.query(DocumentSuggestion)
                .filter(DocumentSuggestion.doc_id == doc_id, DocumentSuggestion.source == "paperless_ocr")
                .one_or_none()
            )
            if stored:
                try:
                    parsed = json.loads(stored.payload)
                    suggestions_by_source["paperless_ocr"] = normalize_suggestions_payload(parsed, tags)
                except Exception:
                    suggestions_by_source["paperless_ocr"] = {"raw": stored.payload}
        if source == "paperless_ocr" and "vision_ocr" not in suggestions_by_source:
            stored = (
                db.query(DocumentSuggestion)
                .filter(DocumentSuggestion.doc_id == doc_id, DocumentSuggestion.source == "vision_ocr")
                .one_or_none()
            )
            if stored:
                try:
                    parsed = json.loads(stored.payload)
                    suggestions_by_source["vision_ocr"] = normalize_suggestions_payload(parsed, tags)
                except Exception:
                    suggestions_by_source["vision_ocr"] = {"raw": stored.payload}
    else:
        stored = (
            db.query(DocumentSuggestion)
            .filter(DocumentSuggestion.doc_id == doc_id)
            .order_by(DocumentSuggestion.source.asc())
            .all()
        )
        for row in stored:
            try:
                parsed = json.loads(row.payload)
                suggestions_by_source[row.source] = normalize_suggestions_payload(parsed, tags)
            except Exception:
                suggestions_by_source[row.source] = {"raw": row.payload}

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


@router.post("/{doc_id}/suggestions/field", response_model=SuggestFieldVariantsResponse)
def suggest_field_variants(
    doc_id: int,
    payload: SuggestionFieldRequest,
    priority: bool = False,
    settings: Settings = Depends(settings_dep),
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
                fetch_pdf_bytes=lambda: paperless.get_document_pdf(settings, doc_id),
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
    if settings.queue_enabled:
        task = {
            "doc_id": doc_id,
            "task": "suggest_field",
            "source": payload.source,
            "field": payload.field,
            "count": max(1, min(payload.count, 5)),
            "current": current,
        }
        if priority:
            enqueue_task_front(settings, task)
        else:
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
    settings: Settings = Depends(settings_dep),
    db: Session = Depends(get_db),
):
    logger = __import__("logging").getLogger(__name__)
    doc = db.get(Document, doc_id)
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
            match = (
                db.query(Correspondent)
                .filter(Correspondent.name.ilike(name))
                .one_or_none()
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


@router.get("/{doc_id}/page-texts", response_model=PageTextsResponse)
def get_document_page_texts(
    doc_id: int,
    priority: bool = False,
    settings: Settings = Depends(settings_dep),
    db: Session = Depends(get_db),
):
    logger = __import__("logging").getLogger(__name__)
    logger.info("Fetch page texts doc=%s", doc_id)
    if priority and settings.queue_enabled:
        enqueue_docs_front(settings, [doc_id])
    raw = paperless.get_document(settings, doc_id)
    content = raw.get("content")
    baseline_pages = get_baseline_page_texts(
        settings,
        content,
        fetch_pdf_bytes=lambda: paperless.get_document_pdf(settings, doc_id),
    )
    vision_pages = (
        db.query(DocumentPageText)
        .filter(DocumentPageText.doc_id == doc_id, DocumentPageText.source == "vision_ocr")
        .order_by(DocumentPageText.page.asc())
        .all()
    )
    pages = []
    for page in baseline_pages:
        quality = score_text_quality(page.text, settings)
        pages.append(
            {
                "page": page.page,
                "source": page.source,
                "text": page.text,
                "quality": {
                    "score": quality.score,
                    "reasons": quality.reasons,
                    "metrics": quality.metrics,
                },
            }
        )
    for page in vision_pages:
        pages.append(
            {
                "page": page.page,
                "source": page.source,
                "text": page.text,
                "quality": {
                    "score": page.quality_score,
                    "reasons": [],
                    "metrics": {},
                },
            }
        )
    pages.sort(key=lambda p: (p.get("page") or 0, str(p.get("source") or "")))
    logger.info("Page texts doc=%s pages=%s", doc_id, len(pages))
    return {
        "doc_id": doc_id,
        "pages": pages,
    }


@router.get("/{doc_id}/page-preview")
def get_document_page_preview(
    doc_id: int,
    page: int,
    max_dim: int | None = None,
    settings: Settings = Depends(settings_dep),
):
    if page < 1:
        raise HTTPException(status_code=400, detail="page must be >= 1")
    if max_dim is None:
        max_dim = settings.vision_ocr_max_dim or 1024
    max_dim = max(256, min(int(max_dim), 2048))
    cache_key = (doc_id, page, max_dim)
    cached = _preview_cache.get(cache_key)
    now = time()
    if cached and now - cached[0] < _preview_cache_ttl:
        return Response(
            content=cached[1],
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=3600"},
        )
    try:
        pdf_bytes = paperless.get_document_pdf(settings, doc_id)
        rendered = render_pdf_pages(pdf_bytes, [page], max_dim=max_dim)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if not rendered:
        raise HTTPException(status_code=404, detail="page not found")
    _preview_cache[cache_key] = (now, rendered[0].image_bytes)
    return Response(
        content=rendered[0].image_bytes,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/{doc_id}/pdf")
def get_document_pdf(
    doc_id: int,
    settings: Settings = Depends(settings_dep),
):
    pdf_bytes = paperless.get_document_pdf(settings, doc_id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Cache-Control": "private, max-age=300"},
    )


@router.post("/process-missing", response_model=ProcessMissingResponse)
def process_missing(
    dry_run: bool = False,
    include_vision_ocr: bool = True,
    include_embeddings: bool = True,
    include_suggestions_paperless: bool = True,
    include_suggestions_vision: bool = True,
    embeddings_mode: str = "auto",
    limit: int | None = None,
    settings: Settings = Depends(settings_dep),
    db: Session = Depends(get_db),
):
    if not settings.queue_enabled:
        return {"enabled": False, "docs": 0, "enqueued": 0, "tasks": 0, "dry_run": dry_run}
    if embeddings_mode not in ("auto", "paperless", "vision"):
        raise HTTPException(status_code=400, detail="Invalid embeddings_mode")
    if limit is not None and limit < 1:
        raise HTTPException(status_code=400, detail="limit must be >= 1")

    docs = db.query(Document).order_by(Document.id.asc()).all()
    if include_vision_ocr:
        docs.sort(
            key=lambda doc: (
                doc.page_count is None,
                doc.page_count or 0,
                doc.id,
            )
        )
    embeddings = {
        row.doc_id: row for row in db.query(DocumentEmbedding).all()
    }
    suggestions = {
        (row.doc_id, row.source): row for row in db.query(DocumentSuggestion).all()
    }
    vision_rows = (
        db.query(DocumentPageText)
        .filter(DocumentPageText.source == "vision_ocr")
        .all()
    )
    vision_latest: dict[int, datetime] = {}
    for row in vision_rows:
        created = _parse_iso(row.created_at)
        if not created:
            continue
        current = vision_latest.get(row.doc_id)
        if current is None or created > current:
            vision_latest[row.doc_id] = created

    enqueued_docs = 0
    enqueued_tasks = 0
    missing_docs = 0
    missing_vision = 0
    missing_embeddings = 0
    missing_embeddings_vision = 0
    missing_sugg_p = 0
    missing_sugg_v = 0
    selected_for_run = 0
    for doc in docs:
        if _should_skip_doc(doc):
            continue
        tasks: list[dict] = []
        doc_modified = _parse_iso(doc.modified) or _parse_iso(doc.created)
        embedding = embeddings.get(doc.id)
        embedded_at = _parse_iso(embedding.embedded_at) if embedding else None
        embedding_source = embedding.embedding_source if embedding else None
        has_vision_embedding = embedding_source == "vision"
        vision_updated_at = vision_latest.get(doc.id)
        has_vision = vision_updated_at is not None

        need_vision_ocr = settings.enable_vision_ocr and not has_vision
        # Continue-processing should only handle missing data (no reprocessing based on timestamps).
        need_embeddings = embedding is None

        if embeddings_mode == "paperless":
            prefer_vision_embeddings = False
        elif embeddings_mode == "vision":
            prefer_vision_embeddings = True
            need_embeddings = not has_vision_embedding
        else:
            prefer_vision_embeddings = settings.enable_vision_ocr and (has_vision or (include_vision_ocr and need_vision_ocr))
            if prefer_vision_embeddings:
                need_embeddings = not has_vision_embedding

        sugg_p = suggestions.get((doc.id, "paperless_ocr"))
        sugg_v = suggestions.get((doc.id, "vision_ocr"))
        sugg_p_at = _parse_iso(sugg_p.created_at) if sugg_p else None
        sugg_v_at = _parse_iso(sugg_v.created_at) if sugg_v else None

        need_sugg_p = sugg_p is None
        need_sugg_v = settings.enable_vision_ocr and (has_vision or need_vision_ocr) and sugg_v is None

        selected = False
        if include_vision_ocr and need_vision_ocr:
            tasks.append({"doc_id": doc.id, "task": "vision_ocr"})
            missing_vision += 1
            selected = True
        if include_embeddings and need_embeddings:
            if embeddings_mode == "paperless":
                task_type = "embeddings_paperless"
            elif embeddings_mode == "vision":
                task_type = "embeddings_vision"
            else:
                task_type = "embeddings_vision" if prefer_vision_embeddings else "embeddings_paperless"
            tasks.append({"doc_id": doc.id, "task": task_type})
            missing_embeddings += 1
            if task_type == "embeddings_vision":
                missing_embeddings_vision += 1
            selected = True
        if include_suggestions_paperless and need_sugg_p:
            tasks.append({"doc_id": doc.id, "task": "suggestions_paperless"})
            missing_sugg_p += 1
            selected = True
        if include_suggestions_vision and need_sugg_v:
            tasks.append({"doc_id": doc.id, "task": "suggestions_vision"})
            missing_sugg_v += 1
            selected = True

        if selected:
            missing_docs += 1
            if not dry_run:
                if limit is None or selected_for_run < limit:
                    enqueued_tasks += enqueue_task_sequence(settings, tasks)
                    enqueued_docs += 1
                    selected_for_run += 1

    return {
        "enabled": True,
        "docs": len(docs),
        "enqueued": enqueued_docs,
        "tasks": enqueued_tasks,
        "dry_run": dry_run,
        "missing_docs": missing_docs,
        "missing_vision_ocr": missing_vision,
        "missing_embeddings": missing_embeddings,
        "missing_embeddings_vision": missing_embeddings_vision,
        "missing_suggestions_paperless": missing_sugg_p,
        "missing_suggestions_vision": missing_sugg_v,
    }


@router.post("/reset-intelligence", response_model=ResetIntelligenceResponse)
def reset_intelligence(
    db: Session = Depends(get_db),
):
    cleared_embeddings = db.query(DocumentEmbedding).count()
    cleared_page_texts = db.query(DocumentPageText).count()
    cleared_suggestions = db.query(DocumentSuggestion).count()
    db.execute(delete(DocumentEmbedding))
    db.execute(delete(DocumentPageText))
    db.execute(delete(DocumentSuggestion))
    db.commit()
    return {
        "cleared_embeddings": cleared_embeddings,
        "cleared_page_texts": cleared_page_texts,
        "cleared_suggestions": cleared_suggestions,
    }


@router.post("/clear-intelligence", response_model=ClearIntelligenceResponse)
def clear_intelligence(
    settings: Settings = Depends(settings_dep),
    db: Session = Depends(get_db),
):
    doc_count = db.query(Document).count()
    doc_ids = [row.doc_id for row in db.query(DocumentEmbedding.doc_id).all()]
    cleared_embeddings = len(doc_ids)
    cleared_page_texts = db.query(DocumentPageText).count()
    cleared_suggestions = db.query(DocumentSuggestion).count()
    db.execute(delete(DocumentEmbedding))
    db.execute(delete(DocumentPageText))
    db.execute(delete(DocumentSuggestion))
    db.execute(delete(SuggestionAudit))
    db.execute(delete(DocumentNote))
    db.execute(delete(document_tags))
    db.execute(delete(Document))
    db.commit()
    qdrant_deleted = 0
    qdrant_errors = 0
    for doc_id in doc_ids:
        try:
            delete_points_for_doc(settings, doc_id)
            qdrant_deleted += 1
        except Exception:
            qdrant_errors += 1
    return {
        "cleared_documents": doc_count,
        "cleared_embeddings": cleared_embeddings,
        "cleared_page_texts": cleared_page_texts,
        "cleared_suggestions": cleared_suggestions,
        "qdrant_deleted": qdrant_deleted,
        "qdrant_errors": qdrant_errors,
    }


@router.post("/delete-vision-ocr", response_model=DeleteVisionOcrResponse)
def delete_vision_ocr(
    db: Session = Depends(get_db),
):
    deleted = (
        db.query(DocumentPageText)
        .filter(DocumentPageText.source == "vision_ocr")
        .count()
    )
    db.execute(delete(DocumentPageText).where(DocumentPageText.source == "vision_ocr"))
    db.commit()
    return {"deleted": deleted}


@router.post("/delete-suggestions", response_model=DeleteSuggestionsResponse)
def delete_suggestions(
    db: Session = Depends(get_db),
):
    deleted = db.query(DocumentSuggestion).count()
    db.execute(delete(DocumentSuggestion))
    db.commit()
    return {"deleted": deleted}


@router.post("/delete-embeddings", response_model=DeleteEmbeddingsResponse)
def delete_embeddings(
    settings: Settings = Depends(settings_dep),
    db: Session = Depends(get_db),
):
    doc_ids = [row.doc_id for row in db.query(DocumentEmbedding.doc_id).all()]
    deleted = len(doc_ids)
    db.execute(delete(DocumentEmbedding))
    db.commit()
    qdrant_deleted = 0
    qdrant_errors = 0
    for doc_id in doc_ids:
        try:
            delete_points_for_doc(settings, doc_id)
            qdrant_deleted += 1
        except Exception:
            qdrant_errors += 1
    return {
        "deleted": deleted,
        "qdrant_deleted": qdrant_deleted,
        "qdrant_errors": qdrant_errors,
    }
