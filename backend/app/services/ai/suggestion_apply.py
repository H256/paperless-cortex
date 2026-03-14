from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import case, func, or_

from app.models import (
    Correspondent,
    DocumentNote,
    DocumentPendingCorrespondent,
    DocumentPendingTag,
    DocumentSuggestion,
    Tag,
)
from app.services.ai.suggestion_operations import format_ai_summary_note
from app.services.documents.note_ids import next_local_note_id
from app.services.runtime.string_list_json import (
    dumps_normalized_string_list,
    normalize_string_list,
    parse_string_list_json,
)
from app.services.runtime.time_utils import utc_now_iso

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.orm import Session

    from app.models import Document


def apply_suggestion_to_document_payload(
    *,
    db: Session,
    doc_id: int,
    source: str | None,
    field: str,
    value: object,
    get_document_or_none_fn: Callable[[Session, int], Document | None],
    audit_suggestion_run_fn: Callable[[Session, int, str, str], None],
) -> dict[str, object]:
    def find_suggestion_meta() -> tuple[str | None, str | None]:
        suggestion_row = None
        if source:
            suggestion_row = (
                db.query(DocumentSuggestion)
                .filter(
                    DocumentSuggestion.doc_id == doc_id,
                    DocumentSuggestion.source == source,
                )
                .one_or_none()
            )
        if not suggestion_row:
            suggestion_row = (
                db.query(DocumentSuggestion)
                .filter(DocumentSuggestion.doc_id == doc_id)
                .order_by(
                    DocumentSuggestion.processed_at.desc().nullslast(),
                    DocumentSuggestion.source.asc(),
                )
                .first()
            )
        if not suggestion_row:
            return None, None
        return suggestion_row.model_name, suggestion_row.processed_at

    doc = get_document_or_none_fn(db, doc_id)
    if not doc:
        return {"status": "missing"}

    updated = False
    details: dict[str, object] = {}

    if field == "title":
        doc.title = str(value).strip() if value is not None else None
        updated = True
    elif field == "date":
        doc.document_date = str(value).strip() if value is not None else None
        updated = True
    elif field == "correspondent":
        pending_row = (
            db.query(DocumentPendingCorrespondent)
            .filter(DocumentPendingCorrespondent.doc_id == doc_id)
            .one_or_none()
        )
        name = str(value).strip() if value is not None else ""
        if name:
            like_term = f"%{name}%"
            match = (
                db.query(Correspondent)
                .filter(Correspondent.name.ilike(like_term))
                .order_by(
                    case((Correspondent.name.ilike(name), 0), else_=1),
                    func.length(Correspondent.name).asc(),
                )
                .first()
            )
            if match:
                doc.correspondent_id = match.id
                if pending_row is not None:
                    db.delete(pending_row)
                updated = True
            else:
                doc.correspondent_id = None
                if pending_row is None:
                    db.add(
                        DocumentPendingCorrespondent(
                            doc_id=doc_id,
                            name=name,
                            updated_at=utc_now_iso(),
                        )
                    )
                    updated = True
                elif (pending_row.name or "").strip() != name:
                    pending_row.name = name
                    pending_row.updated_at = utc_now_iso()
                    updated = True
                details["unmatched"] = name
        else:
            doc.correspondent_id = None
            if pending_row is not None:
                db.delete(pending_row)
            updated = True
    elif field == "tags":
        pending_row = (
            db.query(DocumentPendingTag).filter(DocumentPendingTag.doc_id == doc_id).one_or_none()
        )
        old_pending: list[str] = []
        if pending_row and pending_row.names_json:
            old_pending = parse_string_list_json(pending_row.names_json)
        tag_names: list[str] = []
        if isinstance(value, list):
            tag_names = [str(v).strip() for v in value if str(v).strip()]
        elif isinstance(value, str):
            tag_names = [v.strip() for v in value.split(",") if v.strip()]
        matched: list[Tag] = []
        unmatched: list[str] = []
        for name in tag_names:
            row = db.query(Tag).filter(Tag.name.ilike(name)).one_or_none()
            if row:
                matched.append(row)
            else:
                unmatched.append(name)
        if matched:
            doc.tags = matched
            updated = True
        normalized_unmatched = normalize_string_list(unmatched)
        if normalized_unmatched:
            names_payload = dumps_normalized_string_list(normalized_unmatched)
            if pending_row is None:
                db.add(
                    DocumentPendingTag(
                        doc_id=doc_id,
                        names_json=names_payload,
                        updated_at=utc_now_iso(),
                    )
                )
                updated = True
            else:
                if (pending_row.names_json or "") != names_payload:
                    pending_row.names_json = names_payload
                    pending_row.updated_at = utc_now_iso()
                    updated = True
        elif pending_row is not None:
            db.delete(pending_row)
            updated = True
        if sorted(old_pending, key=str.lower) != normalized_unmatched:
            updated = True
        details["unmatched"] = unmatched
    elif field == "note":
        summary = str(value).strip() if value is not None else ""
        if summary:
            model_name, processed_at = find_suggestion_meta()
            marker_text = format_ai_summary_note(
                summary,
                model_name=model_name,
                processed_at=processed_at,
            )
            existing_note = (
                db.query(DocumentNote)
                .filter(
                    DocumentNote.document_id == doc_id,
                    or_(
                        DocumentNote.note.like("AI_SUMMARY v1 -%"),
                        DocumentNote.note.like("%\nKI-Zusammenfassung"),
                    ),
                )
                .order_by(DocumentNote.id.asc())
                .first()
            )
            if existing_note:
                existing_note.note = marker_text
                existing_note.created = utc_now_iso()
                updated = True
            else:
                db.add(
                    DocumentNote(
                        id=next_local_note_id(db),
                        document_id=doc_id,
                        note=marker_text,
                        created=utc_now_iso(),
                    )
                )
                updated = True

    if updated:
        audit_suggestion_run_fn(db, doc_id, source or "manual", f"apply_to_document:{field}")
        db.commit()
        return {"status": "ok", "updated": True, **details}
    return {"status": "skipped", "updated": False, **details}
