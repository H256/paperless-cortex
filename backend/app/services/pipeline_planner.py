from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import (
    Document,
    DocumentEmbedding,
    DocumentPageAnchor,
    DocumentPageNote,
    DocumentPageText,
    DocumentSuggestion,
)
from app.services.hierarchical_summary import is_large_document


class PipelineOptions(BaseModel):
    include_sync: bool = False
    include_evidence_index: bool = True
    include_vision_ocr: bool = True
    include_embeddings: bool = True
    include_embeddings_paperless: bool = True
    include_embeddings_vision: bool = True
    include_page_notes: bool = True
    include_summary_hierarchical: bool = True
    include_suggestions_paperless: bool = True
    include_suggestions_vision: bool = True
    embeddings_mode: str = "auto"


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    candidate = str(value).strip()
    if not candidate:
        return None
    if candidate.endswith("Z"):
        candidate = f"{candidate[:-1]}+00:00"
    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        return None


def _task_identity(task: dict[str, Any]) -> tuple:
    return (
        int(task.get("doc_id") or 0),
        str(task.get("task") or ""),
        str(task.get("source") or ""),
        bool(task.get("force") or False),
        bool(task.get("clear_first") or False),
    )


def task_signature(task: dict[str, Any]) -> tuple[str, str]:
    return (
        str(task.get("task") or "").strip(),
        str(task.get("source") or "").strip(),
    )


def dedupe_tasks(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple] = set()
    deduped: list[dict[str, Any]] = []
    for task in tasks:
        key = _task_identity(task)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(task)
    return deduped


def post_sync_followup_tasks(doc_id: int, *, settings: Settings, options: PipelineOptions) -> list[dict[str, Any]]:
    normalized = int(doc_id)
    tasks: list[dict[str, Any]] = []
    if options.include_evidence_index:
        tasks.append({"doc_id": normalized, "task": "evidence_index"})
    use_vision = bool(settings.enable_vision_ocr and options.include_vision_ocr)

    if options.include_embeddings:
        if options.embeddings_mode == "paperless":
            if options.include_embeddings_paperless:
                tasks.append({"doc_id": normalized, "task": "embeddings_paperless"})
        elif options.embeddings_mode == "vision":
            if options.include_embeddings_vision and use_vision:
                tasks.append({"doc_id": normalized, "task": "embeddings_vision"})
        elif options.embeddings_mode == "both":
            if options.include_embeddings_paperless:
                tasks.append({"doc_id": normalized, "task": "embeddings_paperless"})
            if options.include_embeddings_vision and use_vision:
                tasks.append({"doc_id": normalized, "task": "embeddings_vision"})
        else:
            if use_vision and options.include_embeddings_vision:
                tasks.append({"doc_id": normalized, "task": "embeddings_vision"})
            elif options.include_embeddings_paperless:
                tasks.append({"doc_id": normalized, "task": "embeddings_paperless"})

    if use_vision:
        if options.include_vision_ocr:
            tasks.append({"doc_id": normalized, "task": "vision_ocr"})
        if options.include_page_notes or options.include_summary_hierarchical:
            tasks.append({"doc_id": normalized, "task": "page_notes_vision"})
        if options.include_summary_hierarchical:
            tasks.append({"doc_id": normalized, "task": "summary_hierarchical", "source": "vision_ocr"})
        if options.include_suggestions_paperless:
            tasks.append({"doc_id": normalized, "task": "suggestions_paperless"})
        if options.include_suggestions_vision:
            tasks.append({"doc_id": normalized, "task": "suggestions_vision"})
    else:
        if options.include_page_notes or options.include_summary_hierarchical:
            tasks.append({"doc_id": normalized, "task": "page_notes_paperless"})
        if options.include_summary_hierarchical:
            tasks.append({"doc_id": normalized, "task": "summary_hierarchical", "source": "paperless_ocr"})
        if options.include_suggestions_paperless:
            tasks.append({"doc_id": normalized, "task": "suggestions_paperless"})

    return dedupe_tasks(tasks)


def _is_vision_complete(doc: Document, pages: set[int]) -> bool:
    expected = int(doc.page_count or 0)
    if expected <= 0:
        return bool(pages)
    bounded = {page for page in pages if 1 <= page <= expected}
    return len(bounded) == expected


def collect_pipeline_cache(db: Session, *, doc_ids: set[int] | None = None) -> dict[str, Any]:
    id_filter = None
    if doc_ids:
        normalized = {int(doc_id) for doc_id in doc_ids if int(doc_id) > 0}
        if normalized:
            id_filter = normalized

    embedding_query = db.query(DocumentEmbedding.doc_id, DocumentEmbedding.embedding_source)
    if id_filter:
        embedding_query = embedding_query.filter(DocumentEmbedding.doc_id.in_(id_filter))
    embeddings: dict[int, str] = {}
    for doc_id, source in embedding_query.yield_per(500):
        embeddings[int(doc_id)] = str(source or "")

    suggestion_query = db.query(DocumentSuggestion.doc_id, DocumentSuggestion.source, DocumentSuggestion.created_at)
    if id_filter:
        suggestion_query = suggestion_query.filter(DocumentSuggestion.doc_id.in_(id_filter))
    suggestions: set[tuple[int, str]] = set()
    hier_summaries: dict[int, str | None] = {}
    for doc_id, source, created_at in suggestion_query.yield_per(500):
        normalized_doc_id = int(doc_id)
        normalized_source = str(source or "")
        suggestions.add((normalized_doc_id, normalized_source))
        if normalized_source == "hier_summary":
            hier_summaries[normalized_doc_id] = str(created_at) if created_at else None

    vision_query = (
        db.query(DocumentPageText.doc_id, DocumentPageText.page, DocumentPageText.created_at)
        .filter(DocumentPageText.source == "vision_ocr")
    )
    if id_filter:
        vision_query = vision_query.filter(DocumentPageText.doc_id.in_(id_filter))
    vision_latest: dict[int, datetime] = {}
    vision_pages_by_doc: dict[int, set[int]] = {}
    for doc_id, page, created_at in vision_query.yield_per(500):
        if page is None:
            continue
        normalized_doc_id = int(doc_id)
        vision_pages_by_doc.setdefault(normalized_doc_id, set()).add(int(page))
        created = _parse_iso(str(created_at) if created_at else None)
        if not created:
            continue
        current = vision_latest.get(normalized_doc_id)
        if current is None or created > current:
            vision_latest[normalized_doc_id] = created

    page_notes_query = db.query(
        DocumentPageNote.doc_id,
        DocumentPageNote.source,
        DocumentPageNote.page,
        DocumentPageNote.status,
        DocumentPageNote.processed_at,
        DocumentPageNote.created_at,
    )
    if id_filter:
        page_notes_query = page_notes_query.filter(DocumentPageNote.doc_id.in_(id_filter))
    page_notes_by_doc_source: dict[tuple[int, str], list[tuple[int, str, str | None, str | None]]] = {}
    for doc_id, source, page, status, processed_at, created_at in page_notes_query.yield_per(500):
        if page is None:
            continue
        key = (int(doc_id), str(source or ""))
        page_notes_by_doc_source.setdefault(key, []).append(
            (
                int(page),
                str(status or ""),
                str(processed_at) if processed_at else None,
                str(created_at) if created_at else None,
            )
        )

    anchors_query = (
        db.query(DocumentPageAnchor.doc_id, DocumentPageAnchor.page, DocumentPageAnchor.status, DocumentPageAnchor.token_count)
        .filter(DocumentPageAnchor.source == "paperless_pdf")
    )
    if id_filter:
        anchors_query = anchors_query.filter(DocumentPageAnchor.doc_id.in_(id_filter))
    anchors_by_doc: dict[int, list[tuple[int, str, int]]] = {}
    for doc_id, page, status, token_count in anchors_query.yield_per(500):
        if page is None:
            continue
        anchors_by_doc.setdefault(int(doc_id), []).append((int(page), str(status or ""), int(token_count or 0)))

    return {
        "embeddings": embeddings,
        "suggestions": suggestions,
        "vision_latest": vision_latest,
        "vision_pages_by_doc": vision_pages_by_doc,
        "page_notes_by_doc_source": page_notes_by_doc_source,
        "anchors_by_doc": anchors_by_doc,
        "hier_summaries": hier_summaries,
    }


def evaluate_doc_pipeline(
    *,
    doc: Document,
    settings: Settings,
    cache: dict[str, Any],
    options: PipelineOptions,
) -> dict[str, Any]:
    tasks: list[dict[str, Any]] = []
    anchors_by_doc: dict[int, list[tuple[int, str, int]]] = cache["anchors_by_doc"]
    anchor_rows = anchors_by_doc.get(int(doc.id), [])
    expected_anchor_pages = int(doc.page_count or 0)
    completed_anchor_pages = {int(page) for page, status, _token_count in anchor_rows if status in {"ok", "no_text_layer"}}
    has_evidence_index = len(completed_anchor_pages) > 0 if expected_anchor_pages <= 0 else len(completed_anchor_pages) >= expected_anchor_pages
    has_text_layer = any(status == "ok" and int(token_count or 0) > 0 for _page, status, token_count in anchor_rows)
    no_text_layer_complete = bool(anchor_rows) and has_evidence_index and not has_text_layer
    anchor_has_errors = any(status == "error" for _page, status, _token_count in anchor_rows)
    evidence_required = not no_text_layer_complete
    needs_evidence_index = options.include_evidence_index and evidence_required and ((not has_evidence_index) or anchor_has_errors)
    if needs_evidence_index:
        tasks.append({"doc_id": int(doc.id), "task": "evidence_index"})

    embeddings: dict[int, str] = cache["embeddings"]
    embedding_source = embeddings.get(int(doc.id))
    suggestions: set[tuple[int, str]] = cache["suggestions"]
    sugg_p = (int(doc.id), "paperless_ocr") in suggestions
    sugg_v = (int(doc.id), "vision_ocr") in suggestions

    vision_latest: dict[int, datetime] = cache["vision_latest"]
    vision_updated_at = vision_latest.get(int(doc.id))
    vision_pages_by_doc: dict[int, set[int]] = cache["vision_pages_by_doc"]
    has_complete_vision = _is_vision_complete(doc, vision_pages_by_doc.get(int(doc.id), set()))
    needs_vision = options.include_vision_ocr and (not has_complete_vision or not vision_updated_at)
    if needs_vision:
        tasks.append({"doc_id": int(doc.id), "task": "vision_ocr"})

    wants_paperless_embeddings = bool(options.include_embeddings and options.include_embeddings_paperless)
    wants_vision_embeddings = bool(
        options.include_embeddings
        and options.include_embeddings_vision
        and settings.enable_vision_ocr
        and (has_complete_vision or options.include_vision_ocr)
    )
    needs_embeddings_paperless = False
    needs_embeddings_vision = False
    if options.include_embeddings:
        mode = (options.embeddings_mode or "auto").strip().lower()
        has_paperless_embedding = embedding_source in {"paperless", "both"}
        has_vision_embedding = embedding_source in {"vision", "both"}
        if mode == "paperless":
            needs_embeddings_paperless = wants_paperless_embeddings and (not has_paperless_embedding)
        elif mode == "vision":
            needs_embeddings_vision = wants_vision_embeddings and (not has_vision_embedding)
        elif mode == "both":
            needs_embeddings_paperless = wants_paperless_embeddings and (not has_paperless_embedding)
            needs_embeddings_vision = wants_vision_embeddings and (not has_vision_embedding)
        else:
            if wants_vision_embeddings:
                needs_embeddings_vision = not has_vision_embedding
            elif wants_paperless_embeddings:
                needs_embeddings_paperless = not has_paperless_embedding
    needs_embeddings = bool(needs_embeddings_paperless or needs_embeddings_vision)
    if needs_embeddings_paperless:
        tasks.append({"doc_id": int(doc.id), "task": "embeddings_paperless"})
    if needs_embeddings_vision:
        tasks.append({"doc_id": int(doc.id), "task": "embeddings_vision"})

    needs_sugg_p = options.include_suggestions_paperless and (not sugg_p)
    needs_sugg_v = options.include_suggestions_vision and (not sugg_v)

    page_notes_source = "vision_ocr" if settings.enable_vision_ocr and options.include_vision_ocr else "paperless_ocr"
    page_notes_task = "page_notes_vision" if page_notes_source == "vision_ocr" else "page_notes_paperless"
    page_notes_by_doc_source: dict[tuple[int, str], list[tuple[int, str, str | None, str | None]]] = cache["page_notes_by_doc_source"]
    note_rows = page_notes_by_doc_source.get((int(doc.id), page_notes_source), [])
    ok_notes = [row for row in note_rows if row[1] == "ok"]
    note_pages = {int(page) for page, _status, _processed_at, _created_at in ok_notes if page is not None and int(page) > 0}
    expected_note_pages = int(doc.page_count or 0)
    notes_complete = len(note_pages) > 0 if expected_note_pages <= 0 else len(note_pages) >= expected_note_pages
    notes_latest_raw = max((_parse_iso(processed_at) or _parse_iso(created_at) for _p, _s, processed_at, created_at in ok_notes), default=None)
    notes_stale = not notes_latest_raw or (page_notes_source == "vision_ocr" and vision_updated_at is not None and notes_latest_raw < vision_updated_at)
    large_doc = is_large_document(page_count=doc.page_count, total_text=doc.content, threshold_pages=settings.large_doc_page_threshold)
    evaluate_page_notes = options.include_page_notes or options.include_summary_hierarchical
    needs_page_notes = evaluate_page_notes and large_doc and (not notes_complete or bool(notes_stale))
    if needs_page_notes and (options.include_page_notes or options.include_summary_hierarchical):
        tasks.append({"doc_id": int(doc.id), "task": page_notes_task})

    hier_summaries: dict[int, str | None] = cache["hier_summaries"]
    summary_at = _parse_iso(hier_summaries.get(int(doc.id)))
    needs_summary = options.include_summary_hierarchical and large_doc and (not summary_at or (notes_latest_raw and summary_at < notes_latest_raw))
    if needs_summary:
        tasks.append({"doc_id": int(doc.id), "task": "summary_hierarchical", "source": page_notes_source})

    if needs_sugg_p:
        tasks.append({"doc_id": int(doc.id), "task": "suggestions_paperless"})
    if needs_sugg_v:
        tasks.append({"doc_id": int(doc.id), "task": "suggestions_vision"})

    return {
        "doc_id": int(doc.id),
        "tasks": tasks,
        "large_doc": large_doc,
        "preferred_source": page_notes_source,
        "needs_vision": needs_vision,
        "needs_embeddings": needs_embeddings,
        "needs_embeddings_paperless": needs_embeddings_paperless,
        "needs_embeddings_vision": needs_embeddings_vision,
        "needs_suggestions_paperless": needs_sugg_p,
        "needs_suggestions_vision": needs_sugg_v,
        "needs_page_notes": needs_page_notes,
        "needs_summary_hierarchical": needs_summary,
        "needs_evidence_index": needs_evidence_index,
        "evidence_required": evidence_required,
        "evidence_no_text_layer": no_text_layer_complete,
    }
