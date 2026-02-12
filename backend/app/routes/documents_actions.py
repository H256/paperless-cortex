from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import get_db
from app.deps import get_settings
from app.models import (
    Document,
    DocumentEmbedding,
    DocumentOcrScore,
    DocumentPageNote,
    DocumentPageText,
    DocumentSectionSummary,
    DocumentSuggestion,
)
from app.services.queue import enqueue_task, enqueue_task_sequence
from app.services.embeddings import delete_points_for_doc
from app.services.hierarchical_summary import is_large_document
from app.services.page_text_store import reclean_page_texts
from app.services.queue_tasks import build_task_sequence
from app.services import paperless
from app.schemas import DocumentIn
from app.routes.sync import _upsert_document
from app.api_models import (
    ClearIntelligenceResponse,
    CleanupTextsResponse,
    DeleteEmbeddingsResponse,
    DocumentOperationEnqueueResponse,
    DocumentResetReprocessResponse,
    DeleteSuggestionsResponse,
    DeleteVisionOcrResponse,
    ProcessMissingResponse,
    ResetIntelligenceResponse,
)
from app.routes.documents_common import parse_iso, should_skip_doc
from app.routes.queue_guard import require_queue_enabled

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_DOC_TASKS = {
    "sync",
    "vision_ocr",
    "cleanup_texts",
    "embeddings_paperless",
    "embeddings_vision",
    "page_notes_paperless",
    "page_notes_vision",
    "summary_hierarchical",
    "suggestions_paperless",
    "suggestions_vision",
}


class DocumentTaskRequest(BaseModel):
    task: str
    source: str | None = None
    force: bool = False
    clear_first: bool = False


class CleanupTextsRequest(BaseModel):
    doc_ids: list[int] | None = None
    source: str | None = None
    clear_first: bool = False
    enqueue: bool = True


def _is_vision_complete(doc: Document, pages: set[int]) -> bool:
    expected = int(doc.page_count or 0)
    if expected <= 0:
        return bool(pages)
    bounded = {page for page in pages if 1 <= page <= expected}
    return len(bounded) == expected


def _clear_intelligence_tables(db: Session) -> None:
    db.execute(delete(DocumentSuggestion))
    db.execute(delete(DocumentPageText))
    db.execute(delete(DocumentEmbedding))
    db.execute(delete(DocumentOcrScore))
    db.execute(delete(DocumentPageNote))
    db.execute(delete(DocumentSectionSummary))
    db.commit()


def _clear_doc_intelligence(db: Session, doc_id: int) -> None:
    db.query(DocumentSuggestion).filter(DocumentSuggestion.doc_id == doc_id).delete(synchronize_session=False)
    db.query(DocumentPageText).filter(DocumentPageText.doc_id == doc_id).delete(synchronize_session=False)
    db.query(DocumentEmbedding).filter(DocumentEmbedding.doc_id == doc_id).delete(synchronize_session=False)
    db.query(DocumentOcrScore).filter(DocumentOcrScore.doc_id == doc_id).delete(synchronize_session=False)
    db.query(DocumentPageNote).filter(DocumentPageNote.doc_id == doc_id).delete(synchronize_session=False)
    db.query(DocumentSectionSummary).filter(DocumentSectionSummary.doc_id == doc_id).delete(
        synchronize_session=False
    )
    db.commit()


@router.post("/process-missing", response_model=ProcessMissingResponse)
def process_missing(
    dry_run: bool = False,
    include_vision_ocr: bool = True,
    include_embeddings: bool = True,
    include_page_notes: bool = False,
    include_summary_hierarchical: bool = False,
    include_suggestions_paperless: bool = True,
    include_suggestions_vision: bool = True,
    embeddings_mode: str = "auto",
    limit: int | None = None,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    if not require_queue_enabled(settings):
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
    embeddings = {row.doc_id: row for row in db.query(DocumentEmbedding).all()}
    suggestions = {(row.doc_id, row.source): row for row in db.query(DocumentSuggestion).all()}
    vision_rows = (
        db.query(DocumentPageText)
        .filter(DocumentPageText.source == "vision_ocr")
        .all()
    )
    vision_latest: dict[int, datetime] = {}
    vision_pages_by_doc: dict[int, set[int]] = {}
    for row in vision_rows:
        vision_pages_by_doc.setdefault(int(row.doc_id), set()).add(int(row.page))
        created = parse_iso(row.created_at)
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
    missing_page_notes = 0
    missing_summary_hier = 0
    missing_sugg_p = 0
    missing_sugg_v = 0
    checked_docs = 0
    page_notes_rows = db.query(DocumentPageNote).all()
    page_notes_by_doc_source: dict[tuple[int, str], list[DocumentPageNote]] = {}
    for row in page_notes_rows:
        page_notes_by_doc_source.setdefault((int(row.doc_id), str(row.source)), []).append(row)
    hier_summaries = {
        int(row.doc_id): row
        for row in db.query(DocumentSuggestion).filter(DocumentSuggestion.source == "hier_summary").all()
    }
    selected_for_run = 0
    for doc in docs:
        if should_skip_doc(doc):
            continue
        checked_docs += 1
        tasks: list[dict] = []
        doc_modified = parse_iso(doc.modified) or parse_iso(doc.created)
        embedding = embeddings.get(doc.id)
        embedded_at = parse_iso(embedding.embedded_at) if embedding else None
        embedding_source = embedding.embedding_source if embedding else None
        has_vision_embedding = embedding_source == "vision"
        vision_updated_at = vision_latest.get(doc.id)
        sugg_p = suggestions.get((doc.id, "paperless_ocr"))
        sugg_v = suggestions.get((doc.id, "vision_ocr"))
        sugg_p_at = parse_iso(sugg_p.created_at) if sugg_p else None
        sugg_v_at = parse_iso(sugg_v.created_at) if sugg_v else None
        has_complete_vision = _is_vision_complete(doc, vision_pages_by_doc.get(doc.id, set()))
        needs_vision = include_vision_ocr and (
            not has_complete_vision
            or not vision_updated_at
            or (doc_modified and vision_updated_at < doc_modified)
        )
        needs_embeddings = include_embeddings and (
            not embedded_at
            or (doc_modified and embedded_at < doc_modified)
            or (embeddings_mode == "vision" and not has_vision_embedding)
        )
        needs_embeddings_vision = include_embeddings and embeddings_mode == "vision" and not has_vision_embedding
        needs_sugg_p = include_suggestions_paperless and (
            not sugg_p_at or (doc_modified and sugg_p_at < doc_modified)
        )
        needs_sugg_v = include_suggestions_vision and (
            not sugg_v_at or (doc_modified and sugg_v_at < doc_modified)
        )
        page_notes_source = "vision_ocr" if settings.enable_vision_ocr and include_vision_ocr else "paperless_ocr"
        page_notes_task = "page_notes_vision" if page_notes_source == "vision_ocr" else "page_notes_paperless"
        note_rows = page_notes_by_doc_source.get((int(doc.id), page_notes_source), [])
        ok_notes = [row for row in note_rows if row.status == "ok"]
        note_pages = {
            int(row.page)
            for row in ok_notes
            if getattr(row, "page", None) is not None and int(row.page) > 0
        }
        expected_note_pages = int(doc.page_count or 0)
        notes_complete = len(note_pages) > 0 if expected_note_pages <= 0 else len(note_pages) >= expected_note_pages
        notes_latest_raw = max(
            (parse_iso(row.processed_at) or parse_iso(row.created_at) for row in ok_notes),
            default=None,
        )
        notes_stale = (
            not notes_latest_raw
            or (doc_modified and notes_latest_raw < doc_modified)
            or (
                page_notes_source == "vision_ocr"
                and vision_updated_at is not None
                and notes_latest_raw < vision_updated_at
            )
        )
        large_doc = is_large_document(
            page_count=doc.page_count,
            total_text=doc.content,
            threshold_pages=settings.large_doc_page_threshold,
        )
        evaluate_page_notes = include_page_notes or include_summary_hierarchical
        needs_page_notes = evaluate_page_notes and large_doc and (not notes_complete or bool(notes_stale))
        summary_row = hier_summaries.get(int(doc.id))
        summary_at = parse_iso(summary_row.created_at) if summary_row else None
        needs_summary = include_summary_hierarchical and large_doc and (
            not summary_at or (doc_modified and summary_at < doc_modified) or (notes_latest_raw and summary_at < notes_latest_raw)
        )
        if needs_vision:
            missing_vision += 1
            tasks.append({"doc_id": doc.id, "task": "vision_ocr"})
        if needs_embeddings:
            missing_embeddings += 1
            if embeddings_mode == "vision":
                tasks.append({"doc_id": doc.id, "task": "embeddings_vision"})
            elif embeddings_mode == "paperless":
                tasks.append({"doc_id": doc.id, "task": "embeddings_paperless"})
            else:
                tasks.append(
                    {
                        "doc_id": doc.id,
                        "task": "embeddings_vision" if settings.enable_vision_ocr else "embeddings_paperless",
                    }
                )
        if needs_embeddings_vision:
            missing_embeddings_vision += 1
        if evaluate_page_notes and needs_page_notes:
            missing_page_notes += 1
        if needs_summary:
            missing_summary_hier += 1
        if needs_page_notes and (include_page_notes or needs_summary):
            tasks.append({"doc_id": doc.id, "task": page_notes_task})
        if needs_summary:
            tasks.append({"doc_id": doc.id, "task": "summary_hierarchical", "source": page_notes_source})
        if needs_sugg_p:
            missing_sugg_p += 1
            tasks.append({"doc_id": doc.id, "task": "suggestions_paperless"})
        if needs_sugg_v:
            missing_sugg_v += 1
            tasks.append({"doc_id": doc.id, "task": "suggestions_vision"})
        if tasks:
            missing_docs += 1
        if limit is not None and selected_for_run >= limit:
            continue
        if tasks:
            selected_for_run += 1
            if not dry_run:
                enqueued_docs += 1
                enqueued_tasks += enqueue_task_sequence(settings, tasks)

    return {
        "enabled": True,
        "docs": checked_docs,
        "missing_docs": missing_docs,
        "missing_vision_ocr": missing_vision,
        "missing_embeddings": missing_embeddings,
        "missing_embeddings_vision": missing_embeddings_vision,
        "missing_page_notes": missing_page_notes,
        "missing_summary_hierarchical": missing_summary_hier,
        "missing_suggestions_paperless": missing_sugg_p,
        "missing_suggestions_vision": missing_sugg_v,
        "selected": selected_for_run,
        "enqueued": enqueued_docs,
        "tasks": enqueued_tasks,
        "dry_run": dry_run,
    }


@router.post("/reset-intelligence", response_model=ResetIntelligenceResponse)
def reset_intelligence(
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    if not require_queue_enabled(settings):
        return {"enabled": False}
    _clear_intelligence_tables(db)
    return {"enabled": True}


@router.post("/clear-intelligence", response_model=ClearIntelligenceResponse)
def clear_intelligence(
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    if not require_queue_enabled(settings):
        return {"enabled": False}
    _clear_intelligence_tables(db)
    return {"enabled": True}


@router.post("/delete/vision-ocr", response_model=DeleteVisionOcrResponse)
def delete_vision_ocr(
    doc_id: int | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(DocumentPageText).filter(DocumentPageText.source == "vision_ocr")
    if doc_id is not None:
        query = query.filter(DocumentPageText.doc_id == doc_id)
    count = query.count()
    query.delete(synchronize_session=False)
    score_query = db.query(DocumentOcrScore).filter(DocumentOcrScore.source == "vision_ocr")
    if doc_id is not None:
        score_query = score_query.filter(DocumentOcrScore.doc_id == doc_id)
    score_query.delete(synchronize_session=False)
    db.commit()
    return {"deleted": count}


@router.post("/delete/suggestions", response_model=DeleteSuggestionsResponse)
def delete_suggestions(
    doc_id: int | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(DocumentSuggestion)
    if doc_id is not None:
        query = query.filter(DocumentSuggestion.doc_id == doc_id)
    count = query.count()
    query.delete(synchronize_session=False)
    db.commit()
    return {"deleted": count}


@router.post("/delete/embeddings", response_model=DeleteEmbeddingsResponse)
def delete_embeddings(
    doc_id: int | None = None,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    if doc_id is not None:
        delete_points_for_doc(settings, doc_id)
        row = db.get(DocumentEmbedding, doc_id)
        if row:
            db.delete(row)
            db.commit()
        return {"deleted": 1}
    db.query(DocumentEmbedding).delete(synchronize_session=False)
    db.commit()
    return {"deleted": 1}


@router.post("/cleanup-texts", response_model=CleanupTextsResponse)
def cleanup_texts(
    payload: CleanupTextsRequest,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    if payload.source and payload.source not in ("paperless_ocr", "vision_ocr", "pdf_text"):
        raise HTTPException(status_code=400, detail="Invalid source")
    doc_ids = [int(doc_id) for doc_id in (payload.doc_ids or []) if int(doc_id) > 0]
    if payload.enqueue:
        if not require_queue_enabled(settings):
            return {"queued": False, "docs": len(doc_ids), "enqueued": 0, "processed": 0, "updated": 0}
        if not doc_ids:
            doc_ids = [int(row.id) for row in db.query(Document.id).all()]
        tasks: list[dict] = []
        for doc_id in doc_ids:
            task: dict[str, object] = {"doc_id": doc_id, "task": "cleanup_texts", "clear_first": payload.clear_first}
            if payload.source:
                task["source"] = payload.source
            tasks.append(task)
        enqueued = enqueue_task_sequence(settings, tasks)
        return {"queued": True, "docs": len(doc_ids), "enqueued": enqueued, "processed": 0, "updated": 0}

    if doc_ids:
        processed_total = 0
        updated_total = 0
        for doc_id in doc_ids:
            result = reclean_page_texts(
                db,
                settings,
                doc_id=doc_id,
                source=payload.source,
                clear_first=payload.clear_first,
            )
            processed_total += result["processed"]
            updated_total += result["updated"]
        return {
            "queued": False,
            "docs": len(doc_ids),
            "enqueued": 0,
            "processed": processed_total,
            "updated": updated_total,
        }

    result = reclean_page_texts(
        db,
        settings,
        doc_id=None,
        source=payload.source,
        clear_first=payload.clear_first,
    )
    docs_count = db.query(DocumentPageText.doc_id).distinct().count()
    return {
        "queued": False,
        "docs": docs_count,
        "enqueued": 0,
        "processed": result["processed"],
        "updated": result["updated"],
    }


@router.post("/{doc_id}/operations/enqueue-task", response_model=DocumentOperationEnqueueResponse)
def enqueue_document_task(
    doc_id: int,
    payload: DocumentTaskRequest,
    settings: Settings = Depends(get_settings),
):
    if payload.task not in ALLOWED_DOC_TASKS:
        raise HTTPException(status_code=400, detail="Invalid task")
    if not require_queue_enabled(settings):
        return {"enabled": False, "enqueued": 0, "task": payload.task, "doc_id": doc_id}
    task: dict[str, object] = {"doc_id": int(doc_id), "task": payload.task}
    if payload.source:
        task["source"] = payload.source
    if payload.force:
        task["force"] = True
    if payload.clear_first:
        task["clear_first"] = True
    enqueued = enqueue_task(settings, task)
    return {"enabled": True, "enqueued": enqueued, "task": payload.task, "doc_id": doc_id}


@router.post("/{doc_id}/operations/reset-and-reprocess", response_model=DocumentResetReprocessResponse)
def reset_and_reprocess_document(
    doc_id: int,
    enqueue: bool = True,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    _clear_doc_intelligence(db, doc_id)
    delete_points_for_doc(settings, doc_id)

    raw = paperless.get_document(settings, doc_id)
    data = DocumentIn.model_validate(raw)
    cache = {"correspondents": set(), "document_types": set(), "tags": set()}
    _upsert_document(db, settings, data, cache)
    db.commit()

    enqueued = 0
    if enqueue and require_queue_enabled(settings):
        tasks = build_task_sequence(settings, doc_id, include_sync=False, force=True)
        enqueued = enqueue_task_sequence(settings, tasks)
    return {"doc_id": doc_id, "synced": True, "reset": True, "enqueued": enqueued}
