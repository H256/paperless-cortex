from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import HTTPException

from app.api_models import WritebackDirectExecuteResponse
from app.models import SuggestionAudit
from app.services.documents.documents_list_cache import invalidate_documents_list_cache
from app.services.writeback.writeback_direct import (
    build_writeback_conflicts,
    execute_direct_selection,
    resolve_direct_selection,
    sync_local_field_from_paperless,
)
from app.services.writeback.writeback_effects import reviewed_timestamp_for_doc
from app.services.writeback.writeback_plan import extract_ai_summary_note
from app.services.writeback.writeback_preview_cache import invalidate_writeback_preview_cache

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.orm import Session

    from app.api_models import (
        WritebackDirectExecuteRequest,
        WritebackDryRunCall,
        WritebackDryRunItem,
    )
    from app.config import Settings
    from app.models import Document


def direct_execute_response(
    settings: Settings,
    db: Session,
    *,
    doc_id: int,
    request: WritebackDirectExecuteRequest,
    local_doc: Document,
    remote_doc: dict[str, Any],
    item: WritebackDryRunItem,
    execute_call: Callable[[Settings, Session, WritebackDryRunCall], None],
    cleanup_pending_rows_after_patch: Callable[[Session, int, dict[str, Any]], None],
) -> WritebackDirectExecuteResponse:
    if not item.changed:
        reviewed_at = reviewed_timestamp_for_doc(settings, db, int(doc_id))
        db.add(
            SuggestionAudit(
                doc_id=int(doc_id),
                action="apply_to_document:writeback",
                source="writeback",
                field=None,
                old_value=None,
                new_value=None,
                created_at=reviewed_at,
            )
        )
        db.commit()
        invalidate_writeback_preview_cache()
        invalidate_documents_list_cache()
        return WritebackDirectExecuteResponse(
            status="no_changes",
            docs_changed=0,
            calls_count=0,
            doc_ids=[],
            calls=[],
            conflicts=[],
        )

    known_modified = (request.known_paperless_modified or "").strip()
    current_modified = str(remote_doc.get("modified") or "").strip()
    needs_conflict_resolution = bool(
        known_modified and current_modified and known_modified != current_modified
    )
    if needs_conflict_resolution and not request.resolutions:
        return WritebackDirectExecuteResponse(
            status="conflicts",
            docs_changed=len(item.changed_fields),
            calls_count=0,
            doc_ids=[],
            calls=[],
            conflicts=build_writeback_conflicts(item),
        )

    resolutions = {str(k): str(v) for k, v in (request.resolutions or {}).items()}
    selection = resolve_direct_selection(
        db=db,
        local_doc=local_doc,
        remote_doc=remote_doc,
        item=item,
        resolutions=resolutions,
        needs_conflict_resolution=needs_conflict_resolution,
        sync_local_field_from_paperless_fn=lambda inner_db, inner_local_doc, inner_remote_doc, field: sync_local_field_from_paperless(
            inner_db,
            inner_local_doc,
            inner_remote_doc,
            field,
            extract_ai_summary_note=extract_ai_summary_note,
        ),
    )

    try:
        calls = execute_direct_selection(
            settings=settings,
            db=db,
            doc_id=doc_id,
            selection=selection,
            execute_call_fn=execute_call,
            cleanup_pending_rows_after_patch_fn=cleanup_pending_rows_after_patch,
        )
    except RuntimeError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if calls or request.resolutions:
        reviewed_at = reviewed_timestamp_for_doc(settings, db, int(doc_id))
        db.add(
            SuggestionAudit(
                doc_id=int(doc_id),
                action="apply_to_document:writeback",
                source="writeback",
                field=None,
                old_value=None,
                new_value=None,
                created_at=reviewed_at,
            )
        )
    db.commit()
    invalidate_writeback_preview_cache()
    invalidate_documents_list_cache()
    return WritebackDirectExecuteResponse(
        status="completed",
        docs_changed=len(item.changed_fields),
        calls_count=len(calls),
        doc_ids=[doc_id] if calls else [],
        calls=calls,
        conflicts=[],
    )
