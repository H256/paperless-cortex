from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Response
from sqlalchemy import and_, exists, func
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import get_db
from app.deps import get_settings
from app.models import (
    Correspondent,
    Document,
    DocumentEmbedding,
    DocumentPendingTag,
    DocumentPageNote,
    DocumentPageText,
    DocumentSuggestion,
    DocumentType,
    SuggestionAudit,
    Tag,
    document_tags,
)
from app.services import paperless
from app.services.hierarchical_summary import is_large_document
from app.services.queue import enqueue_docs_front
from app.services.text_pages import get_baseline_page_texts, score_text_quality
from app.services.ocr_scoring import ensure_document_ocr_score
from app.services.documents import fetch_pdf_bytes, get_document_or_none
from app.routes.queue_guard import require_queue_enabled
from app.api_models import (
    DocumentLocalResponse,
    DocumentStatsResponse,
    DocumentDashboardResponse,
    DocumentsPageResponse,
    DocumentTextQualityResponse,
    DocumentOcrScoresResponse,
    PageTextsResponse,
    PaperlessDocument,
)
import json

router = APIRouter(prefix="/documents", tags=["documents"])


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    if candidate.endswith("Z"):
        candidate = f"{candidate[:-1]}+00:00"
    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        return None


def _normalize_review_status(value: str | None) -> str:
    if value in {"all", "unreviewed", "reviewed", "needs_review"}:
        return value
    return "all"


def _list_documents_from_paperless(
    settings: Settings,
    page: int,
    page_size: int,
    ordering: str | None,
    correspondent__id: int | None,
    tags__id: int | None,
    document_date__gte: str | None,
    document_date__lte: str | None,
    review_status: str,
) -> dict:
    if review_status == "all":
        return paperless.list_documents(
            settings,
            page=page,
            page_size=page_size,
            ordering=ordering,
            correspondent__id=correspondent__id,
            tags__id=tags__id,
            document_date__gte=document_date__gte,
            document_date__lte=document_date__lte,
        )

    all_results: list[dict] = []
    current_page = 1
    fetch_size = max(page_size, 200)
    while True:
        payload = paperless.list_documents(
            settings,
            page=current_page,
            page_size=fetch_size,
            ordering=ordering,
            correspondent__id=correspondent__id,
            tags__id=tags__id,
            document_date__gte=document_date__gte,
            document_date__lte=document_date__lte,
        )
        all_results.extend(payload.get("results", []) or [])
        if not payload.get("next"):
            break
        current_page += 1
    return {"count": len(all_results), "next": None, "previous": None, "results": all_results}


def _apply_derived_fields_and_review_status(
    payload: dict,
    db: Session,
    include_derived: bool,
    review_status: str,
    page: int,
    page_size: int,
) -> dict:
    if not include_derived and review_status == "all":
        return payload

    results = payload.get("results", []) or []
    doc_ids = [doc.get("id") for doc in results if doc.get("id") is not None]
    if not doc_ids:
        payload["results"] = []
        payload["count"] = 0
        payload["next"] = None
        payload["previous"] = None
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
    local_docs = db.query(Document).filter(Document.id.in_(doc_ids)).all()
    local_by_id = {doc.id: doc for doc in local_docs}
    embed_ids = {row.doc_id for row in db.query(DocumentEmbedding).filter(DocumentEmbedding.doc_id.in_(doc_ids)).all()}
    suggestion_rows = db.query(DocumentSuggestion).filter(DocumentSuggestion.doc_id.in_(doc_ids)).all()
    suggestions_by_doc: dict[int, set[str]] = {}
    for row in suggestion_rows:
        suggestions_by_doc.setdefault(row.doc_id, set()).add(row.source)
    vision_pages = {
        row.doc_id
        for row in db.query(DocumentPageText)
        .filter(DocumentPageText.doc_id.in_(doc_ids), DocumentPageText.source == "vision_ocr")
        .all()
    }
    reviewed_rows = (
        db.query(SuggestionAudit.doc_id, func.max(SuggestionAudit.created_at).label("reviewed_at"))
        .filter(SuggestionAudit.doc_id.in_(doc_ids), SuggestionAudit.action.like("apply_to_document:%"))
        .group_by(SuggestionAudit.doc_id)
        .all()
    )
    reviewed_at_by_doc = {int(row.doc_id): row.reviewed_at for row in reviewed_rows}
    pending_tag_rows = (
        db.query(DocumentPendingTag.doc_id, DocumentPendingTag.names_json)
        .filter(DocumentPendingTag.doc_id.in_(doc_ids))
        .all()
    )
    pending_tags_by_doc: dict[int, list[str]] = {}
    for row in pending_tag_rows:
        names: list[str] = []
        raw = row.names_json or ""
        if raw:
            try:
                names = [str(name).strip() for name in json.loads(raw) if str(name).strip()]
            except Exception:
                names = []
        pending_tags_by_doc[int(row.doc_id)] = names

    filtered_results: list[dict] = []
    for doc in results:
        doc_id = doc.get("id")
        if doc_id is None:
            continue
        local_doc = local_by_id.get(doc_id)
        pending_tag_names = pending_tags_by_doc.get(int(doc_id), [])
        doc["local_cached"] = local_doc is not None
        local_overrides = False
        if local_doc:
            local_issue_date = local_doc.document_date or local_doc.created
            remote_issue_date = doc.get("created")
            local_tags = [tag.id for tag in local_doc.tags]
            paperless_tags = doc.get("tags") or []
            if set(local_tags) != set(paperless_tags):
                local_overrides = True
            if local_doc.title and local_doc.title != doc.get("title"):
                local_overrides = True
            if local_issue_date and local_issue_date != remote_issue_date:
                local_overrides = True
            if local_doc.correspondent_id and local_doc.correspondent_id != doc.get("correspondent"):
                local_overrides = True
            if pending_tag_names:
                local_overrides = True
            if local_overrides:
                doc["title"] = local_doc.title
                doc["document_date"] = local_doc.document_date
                doc["created"] = local_issue_date
                doc["correspondent"] = local_doc.correspondent_id
                doc["correspondent_name"] = local_doc.correspondent.name if local_doc.correspondent else None
                doc["tags"] = local_tags
        doc["pending_tag_names"] = pending_tag_names
        doc["local_overrides"] = local_overrides
        doc["has_embeddings"] = doc_id in embed_ids
        doc.update(analysis_by_doc.get(doc_id, {}))
        sources = suggestions_by_doc.get(doc_id, set())
        doc["has_suggestions"] = bool(sources)
        doc["has_suggestions_paperless"] = "paperless_ocr" in sources
        doc["has_suggestions_vision"] = "vision_ocr" in sources
        doc["has_vision_pages"] = doc_id in vision_pages

        reviewed_at_raw = reviewed_at_by_doc.get(doc_id)
        reviewed_at_dt = _parse_iso_datetime(reviewed_at_raw)
        modified_dt = _parse_iso_datetime(doc.get("modified"))
        if local_overrides:
            derived_review_status = "needs_review"
        elif reviewed_at_dt is None:
            derived_review_status = "unreviewed"
        elif modified_dt and modified_dt > reviewed_at_dt:
            derived_review_status = "needs_review"
        else:
            derived_review_status = "reviewed"
        doc["reviewed_at"] = reviewed_at_raw
        doc["review_status"] = derived_review_status
        if review_status == "all" or review_status == derived_review_status:
            filtered_results.append(doc)

    if review_status == "all":
        payload["results"] = filtered_results
        return payload

    total = len(filtered_results)
    start = max(0, (max(1, page) - 1) * max(1, page_size))
    end = start + max(1, page_size)
    payload["count"] = total
    payload["results"] = filtered_results[start:end]
    payload["next"] = None if end >= total else "filtered"
    payload["previous"] = None if start <= 0 else "filtered"
    return payload


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
    review_status: str = "all",
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    normalized_review_status = _normalize_review_status(review_status)
    payload = _list_documents_from_paperless(
        settings,
        page=page,
        page_size=page_size,
        ordering=ordering,
        correspondent__id=correspondent__id,
        tags__id=tags__id,
        document_date__gte=document_date__gte,
        document_date__lte=document_date__lte,
        review_status=normalized_review_status,
    )
    return _apply_derived_fields_and_review_status(
        payload=payload,
        db=db,
        include_derived=include_derived,
        review_status=normalized_review_status,
        page=page,
        page_size=page_size,
    )


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
        {"id": row[0], "name": row[1] or "Untitled", "count": row[2]}
        for row in correspondents_rows
    ]
    if unassigned_count:
        correspondents.append({"id": None, "name": "Unassigned correspondent", "count": unassigned_count})
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
    tags = [{"id": row[0], "name": row[1] or "Untitled", "count": row[2]} for row in tag_rows]
    if untagged_count:
        tags.append({"id": None, "name": "No tags", "count": untagged_count})
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
        {"id": row[0], "name": row[1] or "Untitled", "count": row[2]}
        for row in type_rows
    ]
    if type_unknown:
        document_types.append({"id": None, "name": "No document type", "count": type_unknown})
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
        month = raw_date[:7] if len(raw_date) >= 7 else "Unknown"
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
            "name": correspondents_map.get(corr_id) or ("Unassigned correspondent" if corr_id is None else "Untitled"),
            "count": count,
        }
        for corr_id, count in unprocessed_by_correspondent.items()
    ]
    unprocessed_corr_list.sort(key=lambda item: item["count"], reverse=True)

    monthly_processing = [
        {"label": month, **counts} for month, counts in sorted(monthly.items(), key=lambda item: item[0])
    ]
    if monthly_processing and monthly_processing[0]["label"] == "Unknown":
        monthly_processing = monthly_processing[1:] + [monthly_processing[0]]

    buckets = {
        "1": 0,
        "2-3": 0,
        "4-6": 0,
        "7-10": 0,
        "11-20": 0,
        "21-50": 0,
        "51+": 0,
        "Unknown": 0,
    }
    for (page_count,) in db.query(Document.page_count).all():
        if page_count is None or page_count < 1:
            buckets["Unknown"] += 1
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
def get_local_document(
    doc_id: int,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    doc = get_document_or_none(db, doc_id)
    if not doc:
        return {"status": "missing"}
    preferred_processing_source = "vision_ocr" if settings.enable_vision_ocr else "paperless_ocr"
    expected_embedding_source = "vision" if preferred_processing_source == "vision_ocr" else "paperless"
    embedding_row = db.get(DocumentEmbedding, doc_id)
    has_embeddings = embedding_row is not None
    embedding_source = embedding_row.embedding_source if embedding_row else None
    embedding_chunk_count = int(embedding_row.chunk_count or 0) if embedding_row else 0
    has_embedding_for_preferred_source = bool(
        has_embeddings
        and embedding_chunk_count > 0
        and embedding_source in {expected_embedding_source, "both"}
    )
    suggestion_sources = {
        str(row.source)
        for row in db.query(DocumentSuggestion.source).filter(DocumentSuggestion.doc_id == doc_id).all()
    }
    has_suggestions_paperless = "paperless_ocr" in suggestion_sources
    has_suggestions_vision = "vision_ocr" in suggestion_sources
    has_hierarchical_summary = "hier_summary" in suggestion_sources
    expected_pages = int(doc.page_count or 0) if int(doc.page_count or 0) > 0 else None
    vision_done_pages = (
        db.query(func.count(func.distinct(DocumentPageText.page)))
        .filter(DocumentPageText.doc_id == doc_id, DocumentPageText.source == "vision_ocr")
        .scalar()
    ) or 0
    has_vision_pages = vision_done_pages > 0
    has_complete_vision_pages = vision_done_pages >= expected_pages if expected_pages else has_vision_pages
    page_notes_paperless_done = (
        db.query(func.count(func.distinct(DocumentPageNote.page)))
        .filter(
            DocumentPageNote.doc_id == doc_id,
            DocumentPageNote.source == "paperless_ocr",
            DocumentPageNote.status == "ok",
        )
        .scalar()
    ) or 0
    page_notes_vision_done = (
        db.query(func.count(func.distinct(DocumentPageNote.page)))
        .filter(
            DocumentPageNote.doc_id == doc_id,
            DocumentPageNote.source == "vision_ocr",
            DocumentPageNote.status == "ok",
        )
        .scalar()
    ) or 0
    has_page_notes_paperless = page_notes_paperless_done > 0
    has_page_notes_vision = page_notes_vision_done > 0
    has_complete_page_notes_paperless = (
        page_notes_paperless_done >= expected_pages if expected_pages else has_page_notes_paperless
    )
    has_complete_page_notes_vision = (
        page_notes_vision_done >= expected_pages if expected_pages else has_page_notes_vision
    )
    is_large_doc = is_large_document(
        page_count=doc.page_count,
        total_text=doc.content,
        threshold_pages=settings.large_doc_page_threshold,
    )
    remote_doc = paperless.get_document(settings, doc_id)
    pending_row = (
        db.query(DocumentPendingTag)
        .filter(DocumentPendingTag.doc_id == doc_id)
        .one_or_none()
    )
    pending_tag_names: list[str] = []
    if pending_row and pending_row.names_json:
        try:
            pending_tag_names = [str(name).strip() for name in json.loads(pending_row.names_json) if str(name).strip()]
        except Exception:
            pending_tag_names = []

    local_tags = [tag.id for tag in doc.tags]
    remote_tags = remote_doc.get("tags") or []
    local_issue_date = doc.document_date or doc.created
    remote_issue_date = remote_doc.get("created")
    local_overrides = False
    if set(local_tags) != set(remote_tags):
        local_overrides = True
    if doc.title and doc.title != remote_doc.get("title"):
        local_overrides = True
    if local_issue_date and local_issue_date != remote_issue_date:
        local_overrides = True
    if doc.correspondent_id and doc.correspondent_id != remote_doc.get("correspondent"):
        local_overrides = True
    if pending_tag_names:
        local_overrides = True

    local_modified_dt = _parse_iso_datetime(doc.modified)
    remote_modified_raw = remote_doc.get("modified")
    remote_modified_dt = _parse_iso_datetime(remote_modified_raw)
    sync_status = "synced"
    if local_modified_dt and remote_modified_dt and remote_modified_dt > local_modified_dt:
        sync_status = "stale"

    reviewed_at_raw = (
        db.query(func.max(SuggestionAudit.created_at))
        .filter(
            SuggestionAudit.doc_id == doc_id,
            SuggestionAudit.action.like("apply_to_document:%"),
        )
        .scalar()
    )
    reviewed_at_dt = _parse_iso_datetime(reviewed_at_raw)
    if local_overrides:
        review_status = "needs_review"
    elif reviewed_at_dt is None:
        review_status = "unreviewed"
    elif remote_modified_dt and remote_modified_dt > reviewed_at_dt:
        review_status = "needs_review"
    else:
        review_status = "reviewed"

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
        "tags": local_tags,
        "notes": [{"note": note.note} for note in doc.notes],
        "original_file_name": doc.original_file_name,
        "local_overrides": local_overrides,
        "sync_status": sync_status,
        "review_status": review_status,
        "reviewed_at": reviewed_at_raw,
        "paperless_modified": remote_modified_raw,
        "pending_tag_names": pending_tag_names,
        "has_embeddings": has_embeddings,
        "embedding_source": embedding_source,
        "embedding_chunk_count": embedding_chunk_count,
        "has_embedding_for_preferred_source": has_embedding_for_preferred_source,
        "has_suggestions_paperless": has_suggestions_paperless,
        "has_suggestions_vision": has_suggestions_vision,
        "has_vision_pages": has_vision_pages,
        "vision_pages_done": int(vision_done_pages),
        "vision_pages_expected": expected_pages,
        "has_complete_vision_pages": has_complete_vision_pages,
        "has_page_notes_paperless": has_page_notes_paperless,
        "has_page_notes_vision": has_page_notes_vision,
        "page_notes_paperless_done": int(page_notes_paperless_done),
        "page_notes_vision_done": int(page_notes_vision_done),
        "page_notes_expected": expected_pages,
        "has_complete_page_notes_paperless": has_complete_page_notes_paperless,
        "has_complete_page_notes_vision": has_complete_page_notes_vision,
        "has_hierarchical_summary": has_hierarchical_summary,
        "is_large_document": is_large_doc,
        "preferred_processing_source": preferred_processing_source,
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
