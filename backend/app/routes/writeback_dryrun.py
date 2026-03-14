from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException

from app.api_models import (
    WritebackDirectExecuteRequest,
    WritebackDirectExecuteResponse,
    WritebackDryRunExecuteRequest,
    WritebackDryRunExecuteResponse,
    WritebackDryRunPreviewResponse,
    WritebackExecuteNowRequest,
    WritebackExecuteNowResponse,
    WritebackExecutePendingRequest,
    WritebackExecutePendingResponse,
    WritebackHistoryResponse,
    WritebackJobCreateRequest,
    WritebackJobDeleteResponse,
    WritebackJobDetail,
    WritebackJobExecuteRequest,
    WritebackJobListResponse,
)
from app.db import get_db
from app.deps import get_settings
from app.services.writeback.writeback_apply import execute_writeback_call as _execute_call
from app.services.writeback.writeback_commands import (
    create_job_response as _create_job_response,
)
from app.services.writeback.writeback_commands import (
    dry_run_execute_response as _dry_run_execute_response,
)
from app.services.writeback.writeback_commands import (
    execute_now_response as _execute_now_response,
)
from app.services.writeback.writeback_commands import (
    execute_pending_jobs_response as _execute_pending_jobs_response,
)
from app.services.writeback.writeback_context import (
    load_direct_writeback_context as _load_direct_writeback_context,
)
from app.services.writeback.writeback_direct_execute import (
    direct_execute_response as _direct_execute_response,
)
from app.services.writeback.writeback_effects import (
    cleanup_pending_rows_after_patch as _cleanup_pending_rows_after_patch,
)
from app.services.writeback.writeback_effects import (
    reviewed_timestamp_for_doc as _reviewed_timestamp_for_doc_impl,
)
from app.services.writeback.writeback_job_ops import (
    delete_job_response as _delete_job_response,
)
from app.services.writeback.writeback_job_ops import (
    execute_job_response as _execute_job_response,
)
from app.services.writeback.writeback_job_ops import (
    get_job_detail_response as _get_job_detail_response,
)
from app.services.writeback.writeback_job_ops import (
    history_response as _history_response,
)
from app.services.writeback.writeback_job_ops import (
    list_jobs_response as _list_jobs_response,
)
from app.services.writeback.writeback_queries import (
    preview_response_for_selection as _preview_response_for_selection,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.config import Settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/writeback", tags=["writeback"])


def _reviewed_timestamp_for_doc(settings: Settings, db: Session, doc_id: int) -> str:
    return _reviewed_timestamp_for_doc_impl(settings, db, doc_id)


@router.post("/documents/{doc_id}/execute-direct", response_model=WritebackDirectExecuteResponse)
def execute_writeback_direct_for_document(
    doc_id: int,
    request: WritebackDirectExecuteRequest,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    if not settings.writeback_execute_enabled:
        raise HTTPException(
            status_code=400,
            detail="Real writeback execution is disabled. Set WRITEBACK_EXECUTE_ENABLED=1 to enable it.",
        )
    context = _load_direct_writeback_context(settings, db, doc_id)
    if context is None:
        raise HTTPException(status_code=404, detail="Local document not found")
    local_doc, remote_doc, item = context
    return _direct_execute_response(
        settings,
        db,
        doc_id=doc_id,
        request=request,
        local_doc=local_doc,
        remote_doc=remote_doc,
        item=item,
        execute_call=_execute_call,
        cleanup_pending_rows_after_patch=_cleanup_pending_rows_after_patch,
    )


@router.post("/execute-now", response_model=WritebackExecuteNowResponse)
def execute_writeback_now(
    request: WritebackExecuteNowRequest,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    if not settings.writeback_execute_enabled:
        raise HTTPException(
            status_code=400,
            detail="Real writeback execution is disabled. Set WRITEBACK_EXECUTE_ENABLED=1 to enable it.",
        )
    doc_ids = sorted({int(doc_id) for doc_id in request.doc_ids if int(doc_id) > 0})
    if not doc_ids:
        raise HTTPException(status_code=400, detail="No valid doc_ids provided")
    return _execute_now_response(
        settings,
        db,
        doc_ids=doc_ids,
        execute_call=_execute_call,
        cleanup_pending_rows_after_patch=_cleanup_pending_rows_after_patch,
        reviewed_timestamp_for_doc=_reviewed_timestamp_for_doc,
        logger=logger,
    )


@router.get("/dry-run/preview", response_model=WritebackDryRunPreviewResponse)
def dry_run_preview(
    page: int = 1,
    page_size: int = 20,
    only_changed: bool = True,
    doc_id: int | None = None,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    """Preview pending writeback changes for one document or a paged selection."""
    return _preview_response_for_selection(
        settings,
        db,
        page=page,
        page_size=page_size,
        only_changed=only_changed,
        doc_id=doc_id,
    )


@router.post("/dry-run/execute", response_model=WritebackDryRunExecuteResponse)
def dry_run_execute(
    request: WritebackDryRunExecuteRequest,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    doc_ids = [int(doc_id) for doc_id in request.doc_ids]
    return _dry_run_execute_response(settings, db, doc_ids=doc_ids, logger=logger)


@router.post("/jobs", response_model=WritebackJobDetail)
def create_writeback_job(
    request: WritebackJobCreateRequest,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    """Create a persisted writeback job from the current previewable changes."""
    doc_ids = sorted({int(doc_id) for doc_id in request.doc_ids if int(doc_id) > 0})
    if not doc_ids:
        raise HTTPException(status_code=400, detail="No valid doc_ids provided")
    return _create_job_response(settings, db, doc_ids=doc_ids)


@router.get("/jobs", response_model=WritebackJobListResponse)
def list_writeback_jobs(db: Session = Depends(get_db), limit: int = 100):
    return _list_jobs_response(db, limit=limit)


@router.get("/jobs/{job_id}", response_model=WritebackJobDetail)
def get_writeback_job(job_id: int, db: Session = Depends(get_db)):
    return _get_job_detail_response(db, job_id=job_id)


@router.delete("/jobs/{job_id}", response_model=WritebackJobDeleteResponse)
def delete_writeback_job(job_id: int, db: Session = Depends(get_db)):
    return _delete_job_response(db, job_id=job_id)


@router.post("/jobs/{job_id}/execute", response_model=WritebackJobDetail)
def execute_writeback_job(
    job_id: int,
    request: WritebackJobExecuteRequest,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    if not request.dry_run and not settings.writeback_execute_enabled:
        raise HTTPException(
            status_code=400,
            detail="Real writeback execution is disabled. Set WRITEBACK_EXECUTE_ENABLED=1 to enable it.",
        )
    return _execute_job_response(
        settings,
        db,
        job_id=job_id,
        dry_run=request.dry_run,
        execute_call=_execute_call,
        cleanup_pending_rows_after_patch=_cleanup_pending_rows_after_patch,
        reviewed_timestamp_for_doc=_reviewed_timestamp_for_doc,
        logger=logger,
    )


@router.get("/history", response_model=WritebackHistoryResponse)
def writeback_history(db: Session = Depends(get_db), limit: int = 100):
    return _history_response(db, limit=limit)


@router.post("/jobs/execute-pending", response_model=WritebackExecutePendingResponse)
def execute_pending_writeback_jobs(
    request: WritebackExecutePendingRequest,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    if not request.dry_run and not settings.writeback_execute_enabled:
        raise HTTPException(
            status_code=400,
            detail="Real writeback execution is disabled. Set WRITEBACK_EXECUTE_ENABLED=1 to enable it.",
        )
    return _execute_pending_jobs_response(
        settings,
        db,
        dry_run=request.dry_run,
        limit=max(0, int(request.limit or 0)),
        execute_call=_execute_call,
        cleanup_pending_rows_after_patch=_cleanup_pending_rows_after_patch,
        reviewed_timestamp_for_doc=_reviewed_timestamp_for_doc,
        logger=logger,
    )
