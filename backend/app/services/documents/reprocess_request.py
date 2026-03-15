from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING

import httpx

from app.api_models import DocumentIn

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.orm import Session

    from app.config import Settings


ReferenceCache = dict[str, set[int]]
TaskPayload = dict[str, object]


def reset_and_reprocess_payload(
    *,
    db: Session,
    settings: Settings,
    doc_id: int,
    enqueue: bool,
    queue_enabled: bool,
    clear_document_intelligence_fn: Callable[[Session, int], None],
    delete_points_for_doc_fn: Callable[[Settings, int], None],
    get_document_fn: Callable[[Settings, int], object],
    upsert_document_fn: Callable[[Session, Settings, DocumentIn, ReferenceCache], object],
    invalidate_documents_list_cache_fn: Callable[[], None],
    build_task_sequence_fn: Callable[[Settings, int, bool, bool], list[TaskPayload]],
    enqueue_task_sequence_front_fn: Callable[[Settings, list[TaskPayload]], int],
) -> dict[str, object]:
    clear_document_intelligence_fn(db, doc_id)
    with suppress(httpx.HTTPError, RuntimeError, ValueError):
        delete_points_for_doc_fn(settings, doc_id)

    raw = get_document_fn(settings, doc_id)
    data = DocumentIn.model_validate(raw)
    cache: ReferenceCache = {"correspondents": set(), "document_types": set(), "tags": set()}
    upsert_document_fn(db, settings, data, cache)
    db.commit()
    invalidate_documents_list_cache_fn()

    enqueued = 0
    if enqueue and queue_enabled:
        tasks = build_task_sequence_fn(settings, doc_id, False, True)
        enqueued = enqueue_task_sequence_front_fn(settings, tasks)
    return {"doc_id": doc_id, "synced": True, "reset": True, "enqueued": enqueued}
