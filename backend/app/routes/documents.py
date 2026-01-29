from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import and_, exists
from sqlalchemy.orm import Session

from app.config import Settings, load_settings
from app.db import get_db
import json

from pydantic import BaseModel

from app.models import Document, DocumentPageText, DocumentSuggestion, DocumentEmbedding, Tag, Correspondent
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
from app.services.queue import enqueue_docs_front

router = APIRouter(prefix="/documents", tags=["documents"])


def settings_dep() -> Settings:
    return load_settings()


@router.get("/")
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
        doc["has_embeddings"] = doc_id in embed_ids
        sources = suggestions_by_doc.get(doc_id, set())
        doc["has_suggestions"] = bool(sources)
        doc["has_vision_pages"] = doc_id in vision_pages
    return payload


@router.get("/stats")
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


@router.get("/{doc_id}")
def get_document(doc_id: int, settings: Settings = Depends(settings_dep)):
    return paperless.get_document(settings, doc_id)


@router.get("/{doc_id}/text-quality")
def get_document_text_quality(doc_id: int, settings: Settings = Depends(settings_dep)):
    logger = __import__("logging").getLogger(__name__)
    logger.info("Fetch text quality doc=%s", doc_id)
    if settings.queue_enabled:
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


@router.get("/{doc_id}/suggestions")
def get_document_suggestions(
    doc_id: int,
    source: str | None = None,
    refresh: bool = False,
    settings: Settings = Depends(settings_dep),
    db: Session = Depends(get_db),
):
    logger = __import__("logging").getLogger(__name__)
    logger.info("Fetch suggestions doc=%s source=%s refresh=%s", doc_id, source, refresh)
    raw = paperless.get_document(settings, doc_id)
    tags = get_cached_tags(settings)
    correspondents = get_cached_correspondents(settings)
    if refresh and settings.queue_enabled:
        enqueue_docs_front(settings, [doc_id])

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
        upsert_suggestion(db, doc_id, "paperless_ocr", json.dumps(baseline_suggestions, ensure_ascii=False))
        audit_suggestion_run(db, doc_id, "paperless_ocr", "suggestions_generate")
        return baseline_suggestions

    def run_vision() -> dict[str, object] | None:
        vision_pages = (
            db.query(DocumentPageText)
            .filter(DocumentPageText.doc_id == doc_id, DocumentPageText.source == "vision_ocr")
            .order_by(DocumentPageText.page.asc())
            .all()
        )
        if not vision_pages and settings.enable_vision_ocr:
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
            return None
        vision_text = "\n\n".join(page.text or "" for page in vision_pages)
        vision_suggestions = generate_suggestions(
            settings,
            raw,
            vision_text,
            tags=tags,
            correspondents=correspondents,
        )
        vision_suggestions = normalize_suggestions_payload(vision_suggestions, tags)
        upsert_suggestion(db, doc_id, "vision_ocr", json.dumps(vision_suggestions, ensure_ascii=False))
        audit_suggestion_run(db, doc_id, "vision_ocr", "suggestions_generate")
        return vision_suggestions

    if refresh:
        if source in (None, "paperless_ocr"):
            suggestions_by_source["paperless_ocr"] = run_baseline()
        if source in (None, "vision_ocr"):
            vision = run_vision()
            if vision is not None:
                suggestions_by_source["vision_ocr"] = vision
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

    best = merge_suggestions(
        suggestions_by_source.get("paperless_ocr"),
        suggestions_by_source.get("vision_ocr"),
    )
    if best:
        suggestions_by_source["best_pick"] = best
    return {"doc_id": doc_id, "suggestions": suggestions_by_source}


class SuggestionFieldRequest(BaseModel):
    source: str
    field: str
    count: int = 3


class SuggestionFieldApply(BaseModel):
    source: str
    field: str
    value: object


class ApplySuggestionToDocument(BaseModel):
    source: str | None = None
    field: str
    value: object


@router.post("/{doc_id}/suggestions/field")
def suggest_field_variants(
    doc_id: int,
    payload: SuggestionFieldRequest,
    settings: Settings = Depends(settings_dep),
    db: Session = Depends(get_db),
):
    raw = paperless.get_document(settings, doc_id)
    tags = get_cached_tags(settings)
    correspondents = get_cached_correspondents(settings)
    if settings.queue_enabled:
        enqueue_docs_front(settings, [doc_id])
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


@router.post("/{doc_id}/suggestions/field/apply")
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


@router.post("/{doc_id}/apply-suggestion")
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
    if field not in ("title", "date", "correspondent", "tags"):
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

    if updated:
        audit_suggestion_run(db, doc_id, payload.source or "manual", f"apply_to_document:{field}")
        db.commit()
        logger.info("Applied suggestion to document doc=%s field=%s", doc_id, field)
        return {"status": "ok", "updated": True, **details}
    return {"status": "skipped", "updated": False, **details}


@router.get("/{doc_id}/page-texts")
def get_document_page_texts(
    doc_id: int,
    settings: Settings = Depends(settings_dep),
    db: Session = Depends(get_db),
):
    logger = __import__("logging").getLogger(__name__)
    logger.info("Fetch page texts doc=%s", doc_id)
    if settings.queue_enabled:
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
