from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.orm import Session


def build_dispatch_handler(
    *,
    settings: object,
    db: Session,
    task_type: str,
    doc_id: int,
    task: dict[str, Any] | None,
    run_id: int | None,
    process_sync_only_fn: Callable[[object, Session, int], None],
    process_evidence_index_fn: Callable[..., None],
    process_embeddings_paperless_fn: Callable[..., None],
    process_embeddings_vision_fn: Callable[..., None],
    process_similarity_index_fn: Callable[[object, Session, int], None],
    process_cleanup_texts_fn: Callable[..., None],
    process_page_notes_fn: Callable[..., None],
    process_summary_hierarchical_fn: Callable[..., None],
    process_suggestions_paperless_fn: Callable[[object, Session, int], None],
    process_suggestions_vision_fn: Callable[[object, Session, int], None],
    process_suggest_field_fn: Callable[[object, Session, dict[str, Any]], None],
) -> Callable[[], None] | None:
    handlers = {
        "sync": lambda: process_sync_only_fn(settings, db, doc_id),
        "evidence_index": lambda: process_evidence_index_fn(
            settings,
            db,
            doc_id,
            source=str((task or {}).get("source") or "paperless_pdf"),
            run_id=run_id,
        ),
        "embeddings_paperless": lambda: process_embeddings_paperless_fn(
            settings, db, doc_id, run_id=run_id
        ),
        "embeddings_vision": lambda: process_embeddings_vision_fn(
            settings, db, doc_id, run_id=run_id
        ),
        "similarity_index": lambda: process_similarity_index_fn(settings, db, doc_id),
        "cleanup_texts": lambda: process_cleanup_texts_fn(
            settings,
            db,
            doc_id,
            source=str((task or {}).get("source")) if (task or {}).get("source") else None,
            clear_first=bool((task or {}).get("clear_first")),
        ),
        "page_notes_paperless": lambda: process_page_notes_fn(
            settings, db, doc_id, "paperless_ocr", run_id=run_id
        ),
        "page_notes_vision": lambda: process_page_notes_fn(
            settings, db, doc_id, "vision_ocr", run_id=run_id
        ),
        "summary_hierarchical": lambda: process_summary_hierarchical_fn(
            settings,
            db,
            doc_id,
            str((task or {}).get("source") or "vision_ocr"),
            run_id=run_id,
        ),
        "suggestions_paperless": lambda: process_suggestions_paperless_fn(settings, db, doc_id),
        "suggestions_vision": lambda: process_suggestions_vision_fn(settings, db, doc_id),
        "suggest_field": lambda: process_suggest_field_fn(settings, db, task or {}),
    }
    return handlers.get(task_type)
