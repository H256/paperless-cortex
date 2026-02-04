from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.config import Settings
from app.services import paperless
from app.services.pagination import load_all_pages
from app.services.meta_upsert import upsert_correspondents, upsert_tags

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
