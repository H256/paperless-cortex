from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import httpx

from app.models import Document, DocumentPendingCorrespondent, DocumentPendingTag
from app.services.documents.documents_list_cache import invalidate_documents_list_cache
from app.services.integrations import paperless
from app.services.runtime.time_utils import utc_now_iso
from app.services.writeback.writeback_preview_cache import invalidate_writeback_preview_cache

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.config import Settings

logger = logging.getLogger(__name__)


def cleanup_pending_rows_after_patch(
    db: Session, doc_id: int, patch_payload: dict[str, Any]
) -> None:
    if "tags" in patch_payload:
        pending_row = (
            db.query(DocumentPendingTag)
            .filter(DocumentPendingTag.doc_id == int(doc_id))
            .one_or_none()
        )
        if pending_row:
            db.delete(pending_row)
    if "correspondent" in patch_payload:
        pending_corr_row = (
            db.query(DocumentPendingCorrespondent)
            .filter(DocumentPendingCorrespondent.doc_id == int(doc_id))
            .one_or_none()
        )
        if pending_corr_row:
            db.delete(pending_corr_row)
    if "tags" in patch_payload or "correspondent" in patch_payload:
        invalidate_writeback_preview_cache()
        invalidate_documents_list_cache()


def reviewed_timestamp_for_doc(settings: Settings, db: Session, doc_id: int) -> str:
    try:
        remote_doc = paperless.get_document(settings, int(doc_id))
        modified = str(remote_doc.get("modified") or "").strip()
        if modified:
            local_doc = db.get(Document, int(doc_id))
            if local_doc:
                local_doc.modified = modified
            return modified
    except (httpx.HTTPError, RuntimeError, ValueError):
        logger.warning("Failed to fetch paperless modified for reviewed_at doc=%s", doc_id)
    return utc_now_iso()
