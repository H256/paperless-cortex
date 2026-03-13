from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import selectinload

from app.models import Document, DocumentPendingCorrespondent, DocumentPendingTag
from app.services.integrations import paperless
from app.services.runtime.string_list_json import parse_string_list_json
from app.services.writeback.writeback_preview import build_writeback_item, metadata_maps

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.api_models import WritebackDryRunItem
    from app.config import Settings


def load_direct_writeback_context(
    settings: Settings,
    db: Session,
    doc_id: int,
) -> tuple[Document, dict[str, Any], WritebackDryRunItem] | None:
    local_doc = (
        db.query(Document)
        .options(selectinload(Document.tags), selectinload(Document.notes))
        .filter(Document.id == doc_id)
        .first()
    )
    if not local_doc:
        return None

    correspondents_by_id, tags_by_id = metadata_maps(db)
    pending_row = (
        db.query(DocumentPendingTag)
        .filter(DocumentPendingTag.doc_id == int(doc_id))
        .one_or_none()
    )
    pending_tag_names: list[str] = []
    if pending_row and pending_row.names_json:
        pending_tag_names = parse_string_list_json(pending_row.names_json)

    pending_correspondent_row = (
        db.query(DocumentPendingCorrespondent)
        .filter(DocumentPendingCorrespondent.doc_id == int(doc_id))
        .one_or_none()
    )
    pending_correspondent_name = (
        str(pending_correspondent_row.name or "").strip()
        if pending_correspondent_row
        else ""
    )

    remote_doc = paperless.get_document_cached(settings, doc_id)
    item = build_writeback_item(
        local_doc=local_doc,
        remote_doc=remote_doc,
        correspondents_by_id=correspondents_by_id,
        tags_by_id=tags_by_id,
        pending_tag_names=pending_tag_names,
        pending_correspondent_name=pending_correspondent_name,
    )
    return local_doc, remote_doc, item
