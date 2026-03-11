from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func

from app.models import DocumentNote

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def next_local_note_id(db: Session) -> int:
    min_id = db.query(func.min(DocumentNote.id)).scalar()
    if min_id is None:
        return -1
    try:
        value = int(min_id)
    except (TypeError, ValueError):
        return -1
    if value >= 0:
        return -1
    return value - 1
