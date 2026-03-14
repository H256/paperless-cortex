from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.api_models import DocumentIn
from app.exceptions import DocumentNotFoundError
from app.models import Document
from app.services.documents.sync_operations import upsert_document
from app.services.integrations import paperless

if TYPE_CHECKING:
    import logging

    from sqlalchemy.orm import Session

    from app.config import Settings


def get_or_sync_local_document(
    *,
    db: Session,
    settings: Settings,
    doc_id: int,
    logger: logging.Logger,
) -> Document:
    doc = db.get(Document, int(doc_id))
    if doc:
        return doc
    try:
        raw = paperless.get_document(settings, int(doc_id))
        data = DocumentIn.model_validate(raw)
        cache: dict[str, set[int]] = {
            "correspondents": set(),
            "document_types": set(),
            "tags": set(),
        }
        upsert_document(db, settings, data, cache)
        db.commit()
        doc = db.get(Document, int(doc_id))
        if doc:
            logger.info("Auto-synced missing local document doc_id=%s", doc_id)
            return doc
    except (httpx.HTTPError, RuntimeError, ValidationError, SQLAlchemyError, ValueError):
        logger.warning(
            "Failed to auto-sync missing local document doc_id=%s", doc_id, exc_info=True
        )
    raise DocumentNotFoundError(int(doc_id))
