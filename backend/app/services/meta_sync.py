from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.config import Settings
from app.services import paperless
from app.services.pagination import load_all_pages
from app.services.meta_upsert import upsert_correspondents, upsert_tags
from app.services.meta_upsert import upsert_document_types

logger = logging.getLogger(__name__)


def sync_tags_all(settings: Settings, db: Session, page_size: int = 200) -> tuple[int, int]:
    results = load_all_pages(lambda **kw: paperless.list_tags(settings, **kw), page_size)
    upserted = upsert_tags(db, results)
    db.commit()
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


def sync_tags_page(settings: Settings, db: Session, page: int, page_size: int = 200) -> tuple[int, int]:
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
