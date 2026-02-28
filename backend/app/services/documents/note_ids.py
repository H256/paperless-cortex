from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import DocumentNote


def next_local_note_id(db: Session) -> int:
    min_id = db.query(func.min(DocumentNote.id)).scalar()
    if min_id is None:
        return -1
    try:
        value = int(min_id)
    except Exception:
        return -1
    if value >= 0:
        return -1
    return value - 1
