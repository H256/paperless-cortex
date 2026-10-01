from __future__ import annotations

from typing import TYPE_CHECKING

from app.services.documents.active_document_stats import active_document_stats

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def compute_document_stats(db: Session) -> dict[str, int]:
    """Compute active-document stats (delegates to the shared single source)."""
    return active_document_stats(db)
