from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.services.documents.pagination import load_all_pages
from app.services.integrations import paperless
from app.services.integrations.meta_upsert import (
    prune_missing_tags,
    upsert_correspondents,
    upsert_document_types,
    upsert_tags,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.config import Settings

logger = logging.getLogger(__name__)


def sync_tags_all(settings: Settings, db: Session, page_size: int = 200) -> tuple[int, int]:
    results = load_all_pages(lambda **kw: paperless.list_tags(settings, **kw), page_size)
    upserted = upsert_tags(db, results)
    valid_ids: set[int] = set()
    for raw in results:
        tag_id = raw.get("id")
        if tag_id is not None and isinstance(tag_id, int):
            valid_ids.add(tag_id)
    pruned = prune_missing_tags(db, valid_ids)
    db.commit()
    if pruned:
        logger.info("Tag cache pruned removed=%s", pruned)
    return len(results), upserted


def sync_correspondents_all(
    settings: Settings, db: Session, page_size: int = 200
) -> tuple[int, int]:
    results = load_all_pages(
        lambda **kw: paperless.list_correspondents(settings, **kw), page_size
    )
    upserted = upsert_correspondents(db, results)
    db.commit()
    return len(results), upserted


def sync_tags_page(
    settings: Settings, db: Session, page: int, page_size: int = 200
) -> tuple[int, int]:
    payload = paperless.list_tags(settings, page=page, page_size=page_size)
    results = payload.get("results", []) or []
    upserted = upsert_tags(db, results)
    db.commit()
    return len(results), upserted


def sync_correspondents_page(
    settings: Settings, db: Session, page: int, page_size: int = 200
) -> tuple[int, int]:
    payload = paperless.list_correspondents(settings, page=page, page_size=page_size)
    results = payload.get("results", []) or []
    upserted = upsert_correspondents(db, results)
    db.commit()
    return len(results), upserted


def sync_document_types_page(
    settings: Settings, db: Session, page: int, page_size: int = 200
) -> tuple[int, int]:
    payload = paperless.list_document_types(settings, page=page, page_size=page_size)
    results = payload.get("results", []) or []
    upserted = upsert_document_types(db, results)
    db.commit()
    return len(results), upserted
