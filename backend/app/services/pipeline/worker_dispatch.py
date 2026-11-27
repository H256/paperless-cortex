"""Worker task dispatch: build a handler for a queued task type."""

from __future__ import annotations

import logging
from typing import Any, Callable, Sequence

from sqlalchemy.orm import Session

from app.services.documents.duplicates import scan_document_duplicates
from app.services.documents.page_text_store import reclean_page_texts
from app.services.pipeline.worker_content_tasks import (
    process_page_notes,
    process_summary_hierarchical,
    process_vision_ocr_only,
)
from app.services.pipeline.worker_document_tasks import (
    process_embeddings_paperless,
    process_embeddings_vision,
    process_evidence_index,
    process_similarity_index,
    process_sync_only,
)
from app.services.pipeline.worker_suggestion_tasks import (
    process_suggest_field,
    process_suggestions_paperless,
    process_suggestions_vision,
)

logger = logging.getLogger(__name__)


def build_dispatch_handler(
    *,
    settings: object,
    db: Session,
    task_type: str,
    doc_id: int,
    task: dict[str, Any] | None,
    run_id: int | None,
    is_cancel_requested_fn: Callable[[object], bool],
    get_tags_fn: Callable[[object], Sequence[object]],
    get_correspondents_fn: Callable[[object], Sequence[object]],
    get_document_fn: Callable[[object, int], dict[str, Any]],
    generate_suggestions_fn: Callable[..., dict[str, Any]],
    persist_suggestions_fn: Callable[..., None],
    learn_rules_fn: Callable[[Session, int], dict[str, object]] | None = None,
    generate_field_variants_fn: Callable[..., dict[str, Any] | list[object]],
    upsert_suggestion_fn: Callable[..., None],
    audit_suggestion_run_fn: Callable[..., None],
) -> Callable[[], None] | None:
    """Build the handler for one queued task type.

    Returns None for unknown task types.
    """
    source = task.get("source") if task else None
    clear_first = bool(task.get("clear_first")) if task else False

    handlers: dict[str, Callable[[], None]] = {
        "sync": lambda: process_sync_only(
            settings, db, doc_id, is_cancel_requested_fn=is_cancel_requested_fn
        ),
        "evidence_index": lambda: process_evidence_index(
            settings,
            db,
            doc_id,
            is_cancel_requested_fn=is_cancel_requested_fn,
            run_id=run_id,
        ),
        "embeddings_paperless": lambda: process_embeddings_paperless(
            settings,
            db,
            doc_id,
            is_cancel_requested_fn=is_cancel_requested_fn,
            run_id=run_id,
        ),
        "embeddings_vision": lambda: process_embeddings_vision(
            settings,
            db,
            doc_id,
            is_cancel_requested_fn=is_cancel_requested_fn,
            run_id=run_id,
            embeddings_mode=task.get("embeddings_mode") if task else None,
            force=bool(task.get("force")) if task else False,
        ),
        "similarity_index": lambda: process_similarity_index(
            settings, db, doc_id, is_cancel_requested_fn=is_cancel_requested_fn
        ),
        "cleanup_texts": lambda: (
            logger.info("Worker cancel requested; abort cleanup texts doc=%s", doc_id)
            if is_cancel_requested_fn(settings)
            else reclean_page_texts(
                db,
                settings,
                doc_id=doc_id,
                source=source,
                clear_first=clear_first,
            )
        ),
        "page_notes": lambda: process_page_notes(
            settings,
            db,
            doc_id,
            "paperless_ocr",
            is_cancel_requested_fn=is_cancel_requested_fn,
            run_id=run_id,
        ),
        "summary_hierarchical": lambda: process_summary_hierarchical(
            settings, db, doc_id, "paperless_ocr", run_id=run_id
        ),
        "suggestions_paperless": lambda: process_suggestions_paperless(
            settings,
            db,
            doc_id,
            is_cancel_requested_fn=is_cancel_requested_fn,
            get_tags_fn=get_tags_fn,
            get_correspondents_fn=get_correspondents_fn,
            get_document_fn=get_document_fn,
            generate_suggestions_fn=generate_suggestions_fn,
            persist_suggestions_fn=persist_suggestions_fn,
            learn_rules_fn=learn_rules_fn,
        ),
        "suggestions_vision": lambda: process_suggestions_vision(
            settings,
            db,
            doc_id,
            is_cancel_requested_fn=is_cancel_requested_fn,
            get_tags_fn=get_tags_fn,
            get_correspondents_fn=get_correspondents_fn,
            get_document_fn=get_document_fn,
            generate_suggestions_fn=generate_suggestions_fn,
            persist_suggestions_fn=persist_suggestions_fn,
            process_vision_ocr_only_fn=lambda s, d, i, force=False, run_id=None: (
                process_vision_ocr_only(
                    s,
                    d,
                    i,
                    force=force,
                    run_id=run_id,
                    is_cancel_requested_fn=is_cancel_requested_fn,
                )
            ),
            learn_rules_fn=learn_rules_fn,
        ),
        "suggest_field": lambda: process_suggest_field(
            settings,
            db,
            task or {},
            get_document_fn=get_document_fn,
            get_tags_fn=get_tags_fn,
            get_correspondents_fn=get_correspondents_fn,
            generate_field_variants_fn=generate_field_variants_fn,
            upsert_suggestion_fn=upsert_suggestion_fn,
            audit_suggestion_run_fn=audit_suggestion_run_fn,
        ),
        "duplicate_scan": lambda: scan_document_duplicates(
            settings, db, doc_id, is_cancel_requested_fn=is_cancel_requested_fn
        ),
    }
    return handlers.get(task_type)
