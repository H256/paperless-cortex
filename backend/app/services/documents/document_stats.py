from __future__ import annotations

from typing import TYPE_CHECKING

from app.services.documents.active_document_stats import active_document_stats

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.config import Settings

def compute_document_stats(db: Session, settings: Settings) -> dict[str, int]:
    """Compute active-document stats using the shared coverage policy."""
    return active_document_stats(db, settings.enable_vision_ocr)
