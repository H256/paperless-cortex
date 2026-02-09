from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy import and_, case, exists, func
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import get_db
from app.deps import get_settings
from app.models import (
    Correspondent,
    Document,
    DocumentEmbedding,
    DocumentNote,
    DocumentPageText,
    DocumentSuggestion,
    DocumentType,
    Tag,
    document_tags,
)
from app.services import paperless
from app.services.queue import enqueue_docs_front
from app.services.text_pages import get_baseline_page_texts, score_text_quality
from app.services.ocr_scoring import ensure_document_ocr_score
from app.services.documents import fetch_pdf_bytes, get_document_or_none
from app.routes.queue_guard import require_queue_enabled
from app.api_models import (
    DocumentLocalResponse,
    DocumentStatsResponse,
    DocumentDashboardResponse,
    DocumentSummary,
    DocumentsPageResponse,
    DocumentTextQualityResponse,
    DocumentOcrScoresResponse,
    PageTextsResponse,
    PaperlessDocument,
)
import json

router = APIRouter(prefix="/documents", tags=["documents"])


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
    settings: Settings = Depends(get_settings),
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
    embed_ids = {
        row.doc_id
        for row in db.query(DocumentEmbedding).filter(DocumentEmbedding.doc_id.in_(doc_ids)).all()
    }
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
def get_document(doc_id: int, settings: Settings = Depends(get_settings)):
    return paperless.get_document(settings, doc_id)


@router.get("/{doc_id}/local", response_model=DocumentLocalResponse)
def get_local_document(doc_id: int, db: Session = Depends(get_db)):
    doc = get_document_or_none(db, doc_id)
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
    settings: Settings = Depends(get_settings),
):
    logger = __import__("logging").getLogger(__name__)
    logger.info("Fetch text quality doc=%s", doc_id)
    if priority and require_queue_enabled(settings):
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


@router.get("/{doc_id}/ocr-scores", response_model=DocumentOcrScoresResponse)
def get_document_ocr_scores(
    doc_id: int,
    source: str | None = None,
    refresh: bool = False,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    doc = get_document_or_none(db, doc_id)
    if not doc:
        return {"doc_id": doc_id, "scores": []}
    sources = [source] if source else ["paperless_ocr", "vision_ocr"]
    scores = []
    for src in sources:
        row = ensure_document_ocr_score(settings, db, doc, src, force=refresh)
        if not row:
            continue
        components = {}
        noise = {}
        ppl = {}
        if row.components_json:
            components = json.loads(row.components_json)
        if row.noise_json:
            noise = json.loads(row.noise_json)
        if row.ppl_json:
            ppl = json.loads(row.ppl_json)
        scores.append(
            {
                "source": row.source,
                "verdict": row.verdict,
                "quality_score": row.quality_score,
                "components": components,
                "noise": noise,
                "ppl": ppl,
                "model_name": row.model_name,
                "processed_at": row.processed_at,
            }
        )
    return {"doc_id": doc_id, "scores": scores}


@router.get("/{doc_id}/page-texts", response_model=PageTextsResponse)
def get_document_page_texts(
    doc_id: int,
    priority: bool = False,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    logger = __import__("logging").getLogger(__name__)
    logger.info("Fetch page texts doc=%s", doc_id)
    if priority and require_queue_enabled(settings):
        enqueue_docs_front(settings, [doc_id])
    raw = paperless.get_document(settings, doc_id)
    content = raw.get("content")
    baseline_pages = get_baseline_page_texts(
        settings,
        content,
        fetch_pdf_bytes=lambda: fetch_pdf_bytes(settings, doc_id),
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
    expected_pages_raw = raw.get("page_count")
    expected_pages = int(expected_pages_raw) if isinstance(expected_pages_raw, int) and expected_pages_raw > 0 else None
    vision_page_numbers = {
        int(page.page)
        for page in vision_pages
        if getattr(page, "page", None) is not None and int(page.page) > 0
    }
    if expected_pages is not None:
        bounded_done = {page for page in vision_page_numbers if 1 <= page <= expected_pages}
        done_pages = len(bounded_done)
        missing_pages = max(0, expected_pages - done_pages)
        is_complete = done_pages >= expected_pages
        coverage_percent = round((done_pages / expected_pages) * 100.0, 2) if expected_pages > 0 else None
    else:
        done_pages = len(vision_page_numbers)
        missing_pages = None
        is_complete = False
        coverage_percent = None
    max_page = max(vision_page_numbers) if vision_page_numbers else None
    logger.info("Page texts doc=%s pages=%s", doc_id, len(pages))
    return {
        "doc_id": doc_id,
        "pages": pages,
        "vision_progress": {
            "expected_pages": expected_pages,
            "done_pages": done_pages,
            "missing_pages": missing_pages,
            "max_page": max_page,
            "is_complete": is_complete,
            "coverage_percent": coverage_percent,
        },
    }


@router.get("/{doc_id}/pdf")
def get_document_pdf(
    doc_id: int,
    settings: Settings = Depends(get_settings),
):
    pdf_bytes = fetch_pdf_bytes(settings, doc_id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Cache-Control": "private, max-age=300"},
    )
