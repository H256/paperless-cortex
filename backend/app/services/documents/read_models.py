from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import load_only, selectinload

from app.models import (
    Correspondent,
    Document,
    DocumentEmbedding,
    DocumentPageNote,
    DocumentPageText,
    DocumentPendingCorrespondent,
    DocumentPendingTag,
    DocumentSuggestion,
    SuggestionAudit,
    Tag,
)
from app.services.ai.hierarchical_summary import is_large_document
from app.services.documents.document_review import derive_review_status, derive_sync_status
from app.services.documents.documents import get_document_or_none
from app.services.integrations import paperless
from app.services.runtime.json_utils import parse_json_object
from app.services.runtime.string_list_json import parse_string_list_json
from app.services.writeback.writeback_plan import canonical_ai_summary, extract_ai_summary_note

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.config import Settings

REVIEW_ACTION_MANUAL = "mark_reviewed"


def reviewed_audit_filter() -> Any:
    return or_(
        SuggestionAudit.action.like("apply_to_document:%"),
        SuggestionAudit.action == REVIEW_ACTION_MANUAL,
    )


def normalize_review_status(value: str | None) -> str:
    return value if value in {"all", "unreviewed", "reviewed", "needs_review"} else "all"


def _document_rows(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def _normalized_scalar(value: object) -> object:
    if isinstance(value, str):
        return value.strip()
    return value


def _values_differ(local_value: object, remote_value: object) -> bool:
    return _normalized_scalar(local_value) != _normalized_scalar(remote_value)


def has_local_overrides(
    *,
    local_title: str | None,
    remote_title: str | None,
    local_issue_date: str | None,
    remote_issue_date: str | None,
    local_correspondent_id: int | None,
    remote_correspondent_id: int | None,
    pending_correspondent_name: str | None,
    local_tag_ids: list[int] | None,
    remote_tag_ids: list[int] | None,
    pending_tag_names: list[str] | None,
    local_ai_summary: str | None = None,
    remote_ai_summary: str | None = None,
) -> bool:
    remote_issue_date_norm = _normalized_scalar(remote_issue_date)
    if set(local_tag_ids or []) != set(remote_tag_ids or []):
        return True
    if _values_differ(local_title, remote_title):
        return True
    if remote_issue_date_norm not in (None, "") and _values_differ(
        local_issue_date, remote_issue_date
    ):
        return True
    if _values_differ(local_correspondent_id, remote_correspondent_id):
        return True
    if (pending_correspondent_name or "").strip():
        return True
    if pending_tag_names:
        return True
    return (local_ai_summary or "") != (remote_ai_summary or "")


def list_documents_from_paperless(
    settings: Settings,
    *,
    page: int,
    page_size: int,
    ordering: str | None,
    correspondent__id: int | None,
    tags__id: int | None,
    document_date__gte: str | None,
    document_date__lte: str | None,
    review_status: str,
) -> dict[str, object]:
    missing_correspondent_only = correspondent__id == -1
    effective_correspondent = None if missing_correspondent_only else correspondent__id

    if review_status == "all" and not missing_correspondent_only:
        return paperless.list_documents(
            settings,
            page=page,
            page_size=page_size,
            ordering=ordering,
            correspondent__id=effective_correspondent,
            tags__id=tags__id,
            document_date__gte=document_date__gte,
            document_date__lte=document_date__lte,
        )

    all_results: list[dict[str, object]] = []
    current_page = 1
    fetch_size = max(page_size, 200)
    while True:
        payload = paperless.list_documents_cached(
            settings,
            page=current_page,
            page_size=fetch_size,
            ordering=ordering,
            correspondent__id=effective_correspondent,
            tags__id=tags__id,
            document_date__gte=document_date__gte,
            document_date__lte=document_date__lte,
        )
        batch = _document_rows(payload.get("results", []))
        if missing_correspondent_only:
            batch = [row for row in batch if row.get("correspondent") is None]
        all_results.extend(batch)
        if not payload.get("next"):
            break
        current_page += 1
    if review_status == "all":
        start = max(0, (max(1, page) - 1) * max(1, page_size))
        end = start + max(1, page_size)
        total = len(all_results)
        return {
            "count": total,
            "next": None if end >= total else "filtered",
            "previous": None if start <= 0 else "filtered",
            "results": all_results[start:end],
        }
    return {"count": len(all_results), "next": None, "previous": None, "results": all_results}


def apply_derived_fields_and_review_status(
    *,
    payload: dict[str, object],
    db: Session,
    include_derived: bool,
    include_summary_preview: bool,
    review_status: str,
    page: int,
    page_size: int,
) -> dict[str, object]:
    """Overlay local derived fields and review state onto a Paperless page.

    This is the main enrichment seam for document-list responses: it merges
    local cache state, writeback-pending metadata, processing flags, and
    review-status derivation onto the upstream Paperless result rows.
    """
    if not include_derived and review_status == "all":
        return payload

    results = _document_rows(payload.get("results", []))
    doc_ids = [
        int(raw_doc_id)
        for doc in results
        if (raw_doc_id := doc.get("id")) is not None and isinstance(raw_doc_id, int | str)
    ]
    if not doc_ids:
        payload["results"] = []
        payload["count"] = 0
        payload["next"] = None
        payload["previous"] = None
        return payload

    local_docs = (
        db.query(Document)
        .options(
            load_only(
                Document.id,
                Document.title,
                Document.document_date,
                Document.created,
                Document.correspondent_id,
                Document.analysis_model,
                Document.analysis_processed_at,
            ),
            selectinload(Document.tags).load_only(Tag.id),
            selectinload(Document.correspondent).load_only(Correspondent.name),
        )
        .filter(Document.id.in_(doc_ids))
        .all()
    )
    local_by_id = {int(doc.id): doc for doc in local_docs}
    local_status_rows = (
        db.query(
            Document.id,
            func.max(case((DocumentEmbedding.doc_id.is_not(None), 1), else_=0)).label("has_embeddings"),
            func.max(case((DocumentPageText.doc_id.is_not(None), 1), else_=0)).label("has_vision_pages"),
        )
        .outerjoin(DocumentEmbedding, DocumentEmbedding.doc_id == Document.id)
        .outerjoin(
            DocumentPageText,
            and_(
                DocumentPageText.doc_id == Document.id,
                DocumentPageText.source == "vision_ocr",
            ),
        )
        .filter(Document.id.in_(doc_ids))
        .group_by(Document.id)
        .all()
    )
    local_status_by_doc = {
        int(row.id): {
            "has_embeddings": bool(row.has_embeddings),
            "has_vision_pages": bool(row.has_vision_pages),
        }
        for row in local_status_rows
    }
    reviewed_rows = (
        db.query(SuggestionAudit.doc_id, func.max(SuggestionAudit.created_at).label("reviewed_at"))
        .filter(SuggestionAudit.doc_id.in_(doc_ids), reviewed_audit_filter())
        .group_by(SuggestionAudit.doc_id)
        .all()
    )
    reviewed_at_by_doc = {int(row.doc_id): row.reviewed_at for row in reviewed_rows}
    if include_summary_preview:
        suggestion_rows = (
            db.query(
                DocumentSuggestion.doc_id,
                DocumentSuggestion.source,
                DocumentSuggestion.payload,
            )
            .filter(DocumentSuggestion.doc_id.in_(doc_ids))
            .order_by(DocumentSuggestion.doc_id.asc(), DocumentSuggestion.source.asc())
            .all()
        )
    else:
        suggestion_rows = (
            db.query(DocumentSuggestion.doc_id, DocumentSuggestion.source)
            .filter(DocumentSuggestion.doc_id.in_(doc_ids))
            .group_by(DocumentSuggestion.doc_id, DocumentSuggestion.source)
            .all()
        )
    suggestions_by_doc: dict[int, set[str]] = {}
    for row in suggestion_rows:
        doc_id = int(row[0])
        source = str(row[1] or "")
        suggestions_by_doc.setdefault(doc_id, set()).add(source)
    summary_preview_by_doc: dict[int, str] = {}
    if include_summary_preview:
        for row in suggestion_rows:
            normalized_doc_id = int(row[0])
            if normalized_doc_id in summary_preview_by_doc:
                continue
            preview_payload = row[2]
            parsed_payload = parse_json_object(str(preview_payload or ""))
            summary = parsed_payload.get("summary")
            if not isinstance(summary, str):
                continue
            preview = " ".join(summary.split()).strip()
            if not preview:
                continue
            summary_preview_by_doc[normalized_doc_id] = preview[:240]
    pending_tag_rows = (
        db.query(DocumentPendingTag.doc_id, DocumentPendingTag.names_json)
        .filter(DocumentPendingTag.doc_id.in_(doc_ids))
        .all()
    )
    pending_correspondent_rows = (
        db.query(DocumentPendingCorrespondent.doc_id, DocumentPendingCorrespondent.name)
        .filter(DocumentPendingCorrespondent.doc_id.in_(doc_ids))
        .all()
    )
    pending_tags_by_doc: dict[int, list[str]] = {}
    for row in pending_tag_rows:
        pending_tags_by_doc[int(row.doc_id)] = parse_string_list_json(row.names_json)
    pending_correspondent_by_doc: dict[int, str] = {
        int(row.doc_id): str(row.name or "").strip()
        for row in pending_correspondent_rows
        if str(row.name or "").strip()
    }

    filtered_results: list[dict[str, object]] = []
    for doc in results:
        raw_doc_id = doc.get("id")
        if not isinstance(raw_doc_id, int | str):
            continue
        doc_id = int(raw_doc_id)
        local_doc = local_by_id.get(doc_id)
        pending_tag_names = pending_tags_by_doc.get(doc_id, [])
        pending_correspondent_name = pending_correspondent_by_doc.get(doc_id, "")
        doc["local_cached"] = local_doc is not None
        local_overrides = False
        if local_doc:
            local_issue_date = local_doc.document_date or local_doc.created
            remote_issue_date = doc.get("created")
            local_tags = [int(tag.id) for tag in local_doc.tags]
            raw_tag_ids = doc.get("tags")
            paperless_tags = [
                int(tag_id)
                for tag_id in raw_tag_ids
                if isinstance(tag_id, int)
            ] if isinstance(raw_tag_ids, list) else []
            remote_correspondent_id = doc.get("correspondent")
            local_overrides = has_local_overrides(
                local_title=local_doc.title,
                remote_title=str(doc.get("title") or "") or None,
                local_issue_date=local_issue_date,
                remote_issue_date=str(remote_issue_date) if remote_issue_date else None,
                local_correspondent_id=local_doc.correspondent_id,
                remote_correspondent_id=(
                    int(remote_correspondent_id)
                    if isinstance(remote_correspondent_id, int | str)
                    else None
                ),
                pending_correspondent_name=pending_correspondent_name,
                local_tag_ids=local_tags,
                remote_tag_ids=paperless_tags,
                pending_tag_names=pending_tag_names,
            )
            if local_overrides:
                doc["title"] = local_doc.title
                doc["document_date"] = local_doc.document_date
                doc["created"] = local_issue_date
                doc["correspondent"] = local_doc.correspondent_id
                doc["correspondent_name"] = (
                    local_doc.correspondent.name
                    if local_doc.correspondent
                    else (pending_correspondent_name or None)
                )
                doc["tags"] = local_tags
        doc["pending_tag_names"] = pending_tag_names
        doc["pending_correspondent_name"] = pending_correspondent_name or None
        doc["local_overrides"] = local_overrides
        local_status = local_status_by_doc.get(
            doc_id,
            {"has_embeddings": False, "has_vision_pages": False},
        )
        doc["has_embeddings"] = bool(local_status["has_embeddings"])
        doc["analysis_model"] = local_doc.analysis_model if local_doc else None
        doc["analysis_processed_at"] = local_doc.analysis_processed_at if local_doc else None
        sources = suggestions_by_doc.get(doc_id, set())
        doc["has_suggestions"] = bool(sources)
        doc["has_suggestions_paperless"] = "paperless_ocr" in sources
        doc["has_suggestions_vision"] = "vision_ocr" in sources
        doc["ai_summary_preview"] = summary_preview_by_doc.get(doc_id)
        doc["has_vision_pages"] = bool(local_status["has_vision_pages"])

        reviewed_at_raw = reviewed_at_by_doc.get(doc_id)
        derived = derive_review_status(
            local_overrides=local_overrides,
            reviewed_at=reviewed_at_raw,
            remote_modified=str(doc.get("modified") or "") or None,
        )
        doc["reviewed_at"] = reviewed_at_raw
        doc["review_status"] = derived
        if review_status == "all" or review_status == derived:
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


def build_local_document_payload(
    *,
    doc_id: int,
    settings: Settings,
    db: Session,
) -> dict[str, object]:
    """Build the local document detail payload with processing/review signals."""
    doc = get_document_or_none(db, doc_id)
    if not doc:
        return {"status": "missing"}

    preferred_processing_source = "vision_ocr" if settings.enable_vision_ocr else "paperless_ocr"
    expected_embedding_source = "vision" if preferred_processing_source == "vision_ocr" else "paperless"
    detail_status_row = (
        db.query(
            func.max(DocumentEmbedding.embedding_source).label("embedding_source"),
            func.max(DocumentEmbedding.chunk_count).label("embedding_chunk_count"),
            func.max(case((DocumentSuggestion.source == "paperless_ocr", 1), else_=0)).label(
                "has_suggestions_paperless"
            ),
            func.max(case((DocumentSuggestion.source == "vision_ocr", 1), else_=0)).label(
                "has_suggestions_vision"
            ),
            func.max(case((DocumentSuggestion.source == "hier_summary", 1), else_=0)).label(
                "has_hierarchical_summary"
            ),
            func.count(
                func.distinct(
                    case(
                        (DocumentPageText.source == "vision_ocr", DocumentPageText.page),
                        else_=None,
                    )
                )
            ).label("vision_done_pages"),
            func.count(
                func.distinct(
                    case(
                        (
                            and_(
                                DocumentPageNote.source == "paperless_ocr",
                                DocumentPageNote.status == "ok",
                            ),
                            DocumentPageNote.page,
                        ),
                        else_=None,
                    )
                )
            ).label("page_notes_paperless_done"),
            func.count(
                func.distinct(
                    case(
                        (
                            and_(
                                DocumentPageNote.source == "vision_ocr",
                                DocumentPageNote.status == "ok",
                            ),
                            DocumentPageNote.page,
                        ),
                        else_=None,
                    )
                )
            ).label("page_notes_vision_done"),
            func.max(SuggestionAudit.created_at).label("reviewed_at"),
        )
        .select_from(Document)
        .outerjoin(DocumentEmbedding, DocumentEmbedding.doc_id == Document.id)
        .outerjoin(DocumentSuggestion, DocumentSuggestion.doc_id == Document.id)
        .outerjoin(DocumentPageText, DocumentPageText.doc_id == Document.id)
        .outerjoin(DocumentPageNote, DocumentPageNote.doc_id == Document.id)
        .outerjoin(
            SuggestionAudit,
            and_(
                SuggestionAudit.doc_id == Document.id,
                reviewed_audit_filter(),
            ),
        )
        .filter(Document.id == doc_id)
        .one()
    )
    embedding_source = detail_status_row.embedding_source
    embedding_chunk_count = int(detail_status_row.embedding_chunk_count or 0)
    has_embeddings = embedding_source is not None
    has_embedding_for_preferred_source = bool(
        has_embeddings
        and embedding_chunk_count > 0
        and embedding_source in {expected_embedding_source, "both"}
    )
    has_suggestions_paperless = bool(detail_status_row.has_suggestions_paperless)
    has_suggestions_vision = bool(detail_status_row.has_suggestions_vision)
    has_hierarchical_summary = bool(detail_status_row.has_hierarchical_summary)
    expected_pages = int(doc.page_count or 0) if int(doc.page_count or 0) > 0 else None
    vision_done_pages = int(detail_status_row.vision_done_pages or 0)
    has_vision_pages = vision_done_pages > 0
    has_complete_vision_pages = vision_done_pages >= expected_pages if expected_pages else has_vision_pages
    page_notes_paperless_done = int(detail_status_row.page_notes_paperless_done or 0)
    page_notes_vision_done = int(detail_status_row.page_notes_vision_done or 0)
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
    remote_doc = paperless.get_document_cached(settings, doc_id)
    pending_row = (
        db.query(DocumentPendingTag).filter(DocumentPendingTag.doc_id == doc_id).one_or_none()
    )
    pending_correspondent_row = (
        db.query(DocumentPendingCorrespondent)
        .filter(DocumentPendingCorrespondent.doc_id == doc_id)
        .one_or_none()
    )
    pending_tag_names = parse_string_list_json(pending_row.names_json if pending_row else None)
    pending_correspondent_name = (
        str(pending_correspondent_row.name or "").strip() if pending_correspondent_row else ""
    )

    local_tags = [int(tag.id) for tag in doc.tags]
    remote_tags = [int(tag_id) for tag_id in (remote_doc.get("tags") or []) if isinstance(tag_id, int)]
    local_issue_date = doc.document_date or doc.created
    remote_issue_date = remote_doc.get("created")
    remote_correspondent_id = remote_doc.get("correspondent")
    _, local_ai_note = extract_ai_summary_note(
        [{"id": note.id, "note": note.note} for note in (doc.notes or [])]
    )
    _, remote_ai_note = extract_ai_summary_note(
        remote_doc.get("notes") if isinstance(remote_doc.get("notes"), list) else []
    )
    local_ai_summary = canonical_ai_summary(local_ai_note)
    remote_ai_summary = canonical_ai_summary(remote_ai_note)
    local_overrides = has_local_overrides(
        local_title=doc.title,
        remote_title=str(remote_doc.get("title") or "") or None,
        local_issue_date=local_issue_date,
        remote_issue_date=str(remote_issue_date) if remote_issue_date else None,
        local_correspondent_id=doc.correspondent_id,
        remote_correspondent_id=(
            int(remote_correspondent_id)
            if isinstance(remote_correspondent_id, int | str)
            else None
        ),
        pending_correspondent_name=pending_correspondent_name,
        local_tag_ids=local_tags,
        remote_tag_ids=remote_tags,
        pending_tag_names=pending_tag_names,
        local_ai_summary=local_ai_summary if local_ai_summary else None,
        remote_ai_summary=remote_ai_summary if remote_ai_summary else None,
    )

    remote_modified_raw = remote_doc.get("modified")
    sync_status = derive_sync_status(
        local_modified=doc.modified,
        remote_modified=str(remote_modified_raw) if remote_modified_raw else None,
    )
    reviewed_at_raw = detail_status_row.reviewed_at
    review_status = derive_review_status(
        local_overrides=local_overrides,
        reviewed_at=reviewed_at_raw,
        remote_modified=str(remote_modified_raw) if remote_modified_raw else None,
    )

    return {
        "id": doc.id,
        "title": doc.title,
        "content": doc.content,
        "document_date": doc.document_date,
        "created": doc.created,
        "modified": doc.modified,
        "correspondent": doc.correspondent_id,
        "correspondent_name": (
            doc.correspondent.name if doc.correspondent else (pending_correspondent_name or None)
        ),
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
        "pending_correspondent_name": pending_correspondent_name or None,
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
