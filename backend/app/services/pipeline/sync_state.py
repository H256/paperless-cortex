from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import or_, update

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


def claim_documents_sync(db: Session) -> bool:
    """Atomically claim the document-sync slot; return whether this caller won.

    A single conditional UPDATE is the mutex: it flips the ``documents`` row to
    ``"running"`` only when it is not already running. The winner (``rowcount >
    0``) proceeds; losers return ``False`` and must not touch the in-flight
    state. The existing terminal transitions (idle/error/cancelled) re-open the
    guard, and a stuck ``running`` row is recovered by the cancel endpoint.
    """
    state = get_or_create_state(db, "documents")
    db.flush()  # persist a just-created row before the conditional UPDATE
    result = db.execute(
        update(SyncState)
        .where(
            SyncState.key == "documents",
            or_(SyncState.status.is_(None), SyncState.status != "running"),
        )
        .values(status="running", cancel_requested=False)
    )
    claimed = result.rowcount > 0
    if claimed:
        db.refresh(state)  # sync the in-memory object with the UPDATE result
        ensure_started(state)
    db.commit()
    return claimed
