from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api_models import (
    DuplicateGroupsResponse,
    DuplicateIgnoredResponse,
    DuplicateIgnoreRequest,
    DuplicateIgnoreResponse,
    DuplicateScanResponse,
)
from app.db import get_db
from app.deps import get_settings
from app.models import Document
from app.services.documents.duplicate_scoring import LEVEL_CHECK, LEVELS
from app.services.documents.duplicates import (
    list_duplicate_groups,
    list_ignored_pairs,
    set_pair_ignored,
)
from app.services.pipeline.queue import enqueue_task_sequence
from app.services.pipeline.queue_access import is_queue_enabled

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.config import Settings

router = APIRouter(prefix="/duplicates", tags=["duplicates"])


@router.post("/scan", response_model=DuplicateScanResponse)
def start_duplicate_scan(
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """Queue a duplicate scan task for every non-deleted document."""
    if not is_queue_enabled(settings):
        return {"queued": False, "docs": 0, "enqueued": 0}
    doc_ids = [
        int(row.id)
        for row in db.query(Document.id).filter(Document.deleted_at.is_(None)).yield_per(500)
    ]
    tasks = [{"doc_id": doc_id, "task": "duplicate_scan"} for doc_id in doc_ids]
    enqueued = enqueue_task_sequence(settings, tasks)
    return {"queued": True, "docs": len(doc_ids), "enqueued": int(enqueued)}


@router.get("/groups", response_model=DuplicateGroupsResponse)
def get_duplicate_groups(
    min_level: str = Query(default=LEVEL_CHECK),
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    if min_level not in LEVELS:
        raise HTTPException(status_code=422, detail=f"min_level must be one of {list(LEVELS)}")
    return list_duplicate_groups(db, min_level=min_level, limit=limit)


@router.get("/ignored", response_model=DuplicateIgnoredResponse)
def get_ignored_duplicates(db: Session = Depends(get_db)) -> dict[str, object]:
    return list_ignored_pairs(db)


def _toggle_ignore(payload: DuplicateIgnoreRequest, db: Session, *, ignored: bool) -> dict[str, object]:
    if not set_pair_ignored(db, payload.doc_a_id, payload.doc_b_id, ignored=ignored):
        raise HTTPException(status_code=404, detail="Duplicate pair not found")
    return {"doc_a_id": payload.doc_a_id, "doc_b_id": payload.doc_b_id, "ignored": ignored}


@router.post("/ignore", response_model=DuplicateIgnoreResponse)
def ignore_duplicate_pair(
    payload: DuplicateIgnoreRequest, db: Session = Depends(get_db)
) -> dict[str, object]:
    return _toggle_ignore(payload, db, ignored=True)


@router.post("/unignore", response_model=DuplicateIgnoreResponse)
def unignore_duplicate_pair(
    payload: DuplicateIgnoreRequest, db: Session = Depends(get_db)
) -> dict[str, object]:
    return _toggle_ignore(payload, db, ignored=False)
