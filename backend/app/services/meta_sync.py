from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Correspondent, Tag
from app.schemas import CorrespondentIn, TagIn
from app.services import paperless
from app.services.pagination import load_all_pages

logger = logging.getLogger(__name__)


def sync_tags_all(settings: Settings, db: Session, page_size: int = 200) -> tuple[int, int]:
    results = load_all_pages(lambda **kw: paperless.list_tags(settings, **kw), page_size)
    upserted = 0
    seen: set[int] = set()
    for raw in results:
        data = TagIn.model_validate(raw)
        if data.id in seen:
            continue
        seen.add(data.id)
        tag = db.get(Tag, data.id)
        if not tag:
            tag = Tag(id=data.id)
            db.add(tag)
        tag.name = data.name
        tag.color = data.color
        tag.is_inbox_tag = data.is_inbox_tag
        tag.slug = data.slug
        tag.matching_algorithm = data.matching_algorithm
        tag.is_insensitive = data.is_insensitive
        upserted += 1
    db.commit()
    return len(results), upserted


def sync_correspondents_all(
    settings: Settings, db: Session, page_size: int = 200
) -> tuple[int, int]:
    results = load_all_pages(
        lambda **kw: paperless.list_correspondents(settings, **kw), page_size
    )
    upserted = 0
    seen: set[int] = set()
    for raw in results:
        data = CorrespondentIn.model_validate(raw)
        if data.id in seen:
            continue
        seen.add(data.id)
        correspondent = db.get(Correspondent, data.id)
        if not correspondent:
            correspondent = Correspondent(id=data.id)
            db.add(correspondent)
            db.flush()
        correspondent.name = data.name
        correspondent.slug = data.slug
        correspondent.matching_algorithm = data.matching_algorithm
        correspondent.is_insensitive = data.is_insensitive
        upserted += 1
    db.commit()
    return len(results), upserted
