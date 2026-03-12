from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.models import SyncState

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def get_or_create_state(db: Session, key: str) -> SyncState:
    state = db.get(SyncState, key)
    if not state:
        state = SyncState(key=key)
        db.add(state)
    return state


def mark_running(
    state: SyncState,
    *,
    total: int | None = None,
    processed: int | None = 0,
    reset_cancel: bool = True,
) -> None:
    state.status = "running"
    state.started_at = datetime.now(UTC).isoformat()
    if processed is not None:
        state.processed = processed
    if total is not None:
        state.total = total
    if reset_cancel:
        state.cancel_requested = False


def ensure_started(state: SyncState) -> None:
    if not state.started_at:
        state.started_at = datetime.now(UTC).isoformat()
