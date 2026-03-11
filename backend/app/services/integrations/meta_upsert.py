from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import delete

from app.api_models import CorrespondentIn, DocumentTypeIn, TagIn
from app.models import Correspondent, DocumentType, Tag, document_tags

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def upsert_tags(db: Session, rows: list[dict]) -> int:
    upserted = 0
    seen: set[int] = set()
    for raw in rows:
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
    return upserted


def prune_missing_tags(db: Session, valid_tag_ids: set[int]) -> int:
    if valid_tag_ids:
        db.execute(delete(document_tags).where(~document_tags.c.tag_id.in_(valid_tag_ids)))
        result = db.execute(delete(Tag).where(~Tag.id.in_(valid_tag_ids)))
    else:
        db.execute(delete(document_tags))
        result = db.execute(delete(Tag))
    return int(result.rowcount or 0)


def upsert_correspondents(db: Session, rows: list[dict]) -> int:
    upserted = 0
    seen: set[int] = set()
    for raw in rows:
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
    return upserted


def upsert_document_types(db: Session, rows: list[dict]) -> int:
    upserted = 0
    seen: set[int] = set()
    for raw in rows:
        data = DocumentTypeIn.model_validate(raw)
        if data.id in seen:
            continue
        seen.add(data.id)
        doc_type = db.get(DocumentType, data.id)
        if not doc_type:
            doc_type = DocumentType(id=data.id)
            db.add(doc_type)
        doc_type.name = data.name
        doc_type.slug = data.slug
        doc_type.matching_algorithm = data.matching_algorithm
        doc_type.is_insensitive = data.is_insensitive
        upserted += 1
    return upserted
