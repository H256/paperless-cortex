from __future__ import annotations

from typing import TYPE_CHECKING

from app.api_models import WritebackDryRunPreviewResponse
from app.services.integrations import paperless
from app.services.writeback.writeback_preview import (
    local_writeback_candidate_doc_ids,
    preview_for_doc_ids,
)
from app.services.writeback.writeback_preview_cache import (
    get_cached_writeback_candidate_doc_ids,
    get_cached_writeback_preview,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.config import Settings


def preview_response_for_selection(
    settings: Settings,
    db: Session,
    *,
    page: int,
    page_size: int,
    only_changed: bool,
    doc_id: int | None,
) -> WritebackDryRunPreviewResponse:
    if doc_id is not None and doc_id > 0:
        doc_ids = [int(doc_id)]
        total_count = 1
    elif only_changed:
        candidate_ids = get_cached_writeback_candidate_doc_ids(
            build_candidates=lambda: local_writeback_candidate_doc_ids(db)
        )
        total_count = len(candidate_ids)
        start = max(0, (max(1, page) - 1) * max(1, page_size))
        end = start + max(1, page_size)
        doc_ids = candidate_ids[start:end]
    else:
        payload = paperless.list_documents_cached(settings, page=page, page_size=page_size)
        results = payload.get("results") or []
        doc_ids = [int(doc["id"]) for doc in results if isinstance(doc.get("id"), int)]
        total_count = int(payload.get("count") or 0)

    items = get_cached_writeback_preview(
        doc_ids=doc_ids,
        build_preview=lambda: preview_for_doc_ids(settings, db, doc_ids),
    )
    if only_changed:
        items = [item for item in items if item.changed]
    return WritebackDryRunPreviewResponse(
        count=total_count,
        page=page,
        page_size=page_size,
        items=items,
    )
