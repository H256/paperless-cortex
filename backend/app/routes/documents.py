from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Response

from app.api_models import (
    DocumentDashboardResponse,
    DocumentLocalResponse,
    DocumentMarkReviewedResponse,
    DocumentOcrScoresResponse,
    DocumentsPageResponse,
    DocumentStatsResponse,
    DocumentTextQualityResponse,
    PageTextsResponse,
    PaperlessDocument,
)
from app.db import get_db
from app.deps import get_settings
from app.models import (
    DocumentPageText,
    SuggestionAudit,
)
from app.services.ai.ocr_scoring import ensure_document_ocr_score
from app.services.documents.dashboard import build_dashboard_payload
from app.services.documents.dashboard_cache import (
    get_cached_dashboard_payload,
    invalidate_dashboard_cache,
)
from app.services.documents.document_stats import compute_document_stats
from app.services.documents.document_stats_cache import (
    get_cached_document_stats,
    invalidate_document_stats_cache,
)
from app.services.documents.documents import fetch_pdf_bytes, get_document_or_none
from app.services.documents.documents_list_cache import (
    get_cached_documents_page,
    invalidate_documents_list_cache,
)
from app.services.documents.read_models import (
    REVIEW_ACTION_MANUAL,
    apply_derived_fields_and_review_status,
    build_local_document_payload,
    list_documents_from_paperless,
    normalize_review_status,
)
from app.services.documents.text_pages import get_baseline_page_texts, score_text_quality
from app.services.integrations import paperless
from app.services.pipeline.queue import enqueue_docs_front
from app.services.pipeline.queue_access import is_queue_enabled
from app.services.runtime.json_utils import parse_json_object

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.config import Settings

require_queue_enabled = is_queue_enabled
router = APIRouter(prefix="/documents", tags=["documents"])
logger = logging.getLogger(__name__)


def _documents_list_cache_key(
    *,
    page: int,
    page_size: int,
    ordering: str | None,
    correspondent_id: int | None,
    tags_id: int | None,
    document_date_gte: str | None,
    document_date_lte: str | None,
    include_derived: bool,
    include_summary_preview: bool,
    review_status: str,
) -> tuple[int, int, str | None, int | None, int | None, str | None, str | None, bool, bool, str]:
    return (
        int(page),
        int(page_size),
        ordering,
        correspondent_id,
        tags_id,
        document_date_gte,
        document_date_lte,
        include_derived,
        include_summary_preview,
        review_status,
    )


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
    include_summary_preview: bool = False,
    review_status: str = "all",
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """List Paperless documents with optional local derived state overlays.

    The route preserves the upstream Paperless pagination contract for the
    unfiltered path and falls back to local post-filtering when review-status
    semantics require derived state from the local cache.
    """
    normalized_review_status = normalize_review_status(review_status)

    def _build_payload() -> dict[str, object]:
        missing_correspondent_only = correspondent__id == -1
        effective_correspondent = None if missing_correspondent_only else correspondent__id
        if normalized_review_status != "all":
            current_page = 1
            fetch_size = max(page_size, 200)
            start = max(0, (max(1, page) - 1) * max(1, page_size))
            end = start + max(1, page_size)
            filtered_total = 0
            selected_results: list[dict] = []
            while True:
                batch_payload = paperless.list_documents_cached(
                    settings,
                    page=current_page,
                    page_size=fetch_size,
                    ordering=ordering,
                    correspondent__id=effective_correspondent,
                    tags__id=tags__id,
                    document_date__gte=document_date__gte,
                    document_date__lte=document_date__lte,
                )
                enriched_payload = apply_derived_fields_and_review_status(
                    payload={"results": batch_payload.get("results", []) or []},
                    db=db,
                    include_derived=True,
                    include_summary_preview=include_summary_preview,
                    review_status="all",
                    page=1,
                    page_size=fetch_size,
                )
                enriched_results = enriched_payload.get("results", [])
                batch_results = [
                    row for row in enriched_results if isinstance(row, dict)
                ] if isinstance(enriched_results, list) else []
                if missing_correspondent_only:
                    batch_results = [row for row in batch_results if row.get("correspondent") is None]
                matching = [
                    row for row in batch_results if row.get("review_status") == normalized_review_status
                ]
                batch_count = len(matching)
                if batch_count > 0 and len(selected_results) < max(1, page_size):
                    batch_start = max(0, start - filtered_total)
                    batch_end = max(0, end - filtered_total)
                    if batch_start < batch_count:
                        selected_results.extend(matching[batch_start:batch_end])
                filtered_total += batch_count
                if not batch_payload.get("next"):
                    break
                current_page += 1
            return {
                "count": filtered_total,
                "next": None if end >= filtered_total else "filtered",
                "previous": None if start <= 0 else "filtered",
                "results": selected_results[: max(1, page_size)],
            }

        payload = list_documents_from_paperless(
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
        return apply_derived_fields_and_review_status(
            payload=payload,
            db=db,
            include_derived=include_derived,
            include_summary_preview=include_summary_preview,
            review_status=normalized_review_status,
            page=page,
            page_size=page_size,
        )

    if not include_derived and normalized_review_status == "all":
        return _build_payload()

    return get_cached_documents_page(
        cache_key=_documents_list_cache_key(
            page=page,
            page_size=page_size,
            ordering=ordering,
            correspondent_id=correspondent__id,
            tags_id=tags__id,
            document_date_gte=document_date__gte,
            document_date_lte=document_date__lte,
            include_derived=include_derived,
            include_summary_preview=include_summary_preview,
            review_status=normalized_review_status,
        ),
        build_payload=_build_payload,
    )


@router.get("/stats", response_model=DocumentStatsResponse)
def get_document_stats(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Return aggregate processing counters for the local document cache."""
    return get_cached_document_stats(db, build_payload=compute_document_stats)


@router.get("/dashboard", response_model=DocumentDashboardResponse)
def get_dashboard(db: Session = Depends(get_db)) -> dict[str, object]:
    """Return the cached dashboard payload used by the operations views."""
    return get_cached_dashboard_payload(db, build_payload=build_dashboard_payload)


@router.get("/{doc_id}", response_model=PaperlessDocument)
def get_document(doc_id: int, settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    return paperless.get_document_cached(settings, doc_id)


@router.get("/{doc_id}/local", response_model=DocumentLocalResponse)
def get_local_document(
    doc_id: int,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """Return the local document view with derived processing and review state."""
    return build_local_document_payload(doc_id=doc_id, settings=settings, db=db)


@router.post("/{doc_id}/review/mark", response_model=DocumentMarkReviewedResponse)
def mark_document_reviewed(
    doc_id: int,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    doc = get_document_or_none(db, doc_id)
    if not doc:
        return {"status": "missing", "doc_id": int(doc_id), "reviewed_at": None}
    reviewed_at = datetime.now(UTC).isoformat()
    db.add(
        SuggestionAudit(
            doc_id=int(doc_id),
            action=REVIEW_ACTION_MANUAL,
            source="manual",
            created_at=reviewed_at,
        )
    )
    db.commit()
    invalidate_dashboard_cache()
    invalidate_document_stats_cache()
    invalidate_documents_list_cache()
    return {"status": "ok", "doc_id": int(doc_id), "reviewed_at": reviewed_at}


@router.get("/{doc_id}/text-quality", response_model=DocumentTextQualityResponse)
def get_document_text_quality(
    doc_id: int,
    priority: bool = False,
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    logger.info("Fetch text quality doc=%s", doc_id)
    if priority and require_queue_enabled(settings):
        enqueue_docs_front(settings, [doc_id])
    raw = paperless.get_document_cached(settings, doc_id)
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
) -> dict[str, object]:
    doc = get_document_or_none(db, doc_id)
    if not doc:
        return {"doc_id": doc_id, "scores": []}
    sources = [source] if source else ["paperless_ocr", "vision_ocr"]
    scores = []
    for src in sources:
        row = ensure_document_ocr_score(settings, db, doc, src, force=refresh)
        if not row:
            continue
        components = parse_json_object(row.components_json)
        noise = parse_json_object(row.noise_json)
        ppl = parse_json_object(row.ppl_json)
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
) -> dict[str, object]:
    logger.info("Fetch page texts doc=%s", doc_id)
    if priority and require_queue_enabled(settings):
        enqueue_docs_front(settings, [doc_id])
    raw = paperless.get_document_cached(settings, doc_id)
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
        vision_text = (
            page.clean_text
            if isinstance(page.clean_text, str) and page.clean_text.strip()
            else page.text
        )
        pages.append(
            {
                "page": page.page,
                "source": page.source,
                "text": vision_text,
                "quality": {
                    "score": page.quality_score,
                    "reasons": [],
                    "metrics": {},
                },
            }
        )
    pages.sort(key=lambda p: (p.get("page") or 0, str(p.get("source") or "")))
    expected_pages_raw = raw.get("page_count")
    expected_pages = (
        int(expected_pages_raw)
        if isinstance(expected_pages_raw, int) and expected_pages_raw > 0
        else None
    )
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
        coverage_percent = (
            round((done_pages / expected_pages) * 100.0, 2) if expected_pages > 0 else None
        )
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
) -> Response:
    pdf_bytes = fetch_pdf_bytes(settings, doc_id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Cache-Control": "private, max-age=300"},
    )
