from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.models import Document, DocumentType, Tag
from app.services.documents.read_models import reviewed_audit_filter

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# How many of each pattern type to surface to the model.
_RULE_TOP_N = 5


def _reviewed_doc_ids(db: Session, correspondent_id: int) -> list[int]:
    """Local doc ids of a correspondent that a reviewer confirmed (reviewed)."""
    from app.models import SuggestionAudit

    rows = (
        db.query(SuggestionAudit.doc_id)
        .filter(
            SuggestionAudit.doc_id.in_(
                db.query(Document.id).filter(Document.correspondent_id == correspondent_id)
            ),
            reviewed_audit_filter(),
        )
        .all()
    )
    return [int(row.doc_id) for row in rows if row.doc_id is not None]


def _top_tag_names(db: Session, doc_ids: list[int]) -> list[str]:
    """Most frequent tag names attached to the given docs (via the secondary table)."""
    from app.models import document_tags

    if not doc_ids:
        return []
    counts: dict[str, int] = {}
    rows = (
        db.query(document_tags.c.tag_id)
        .filter(document_tags.c.document_id.in_(doc_ids))
        .all()
    )
    tag_ids = [int(row.tag_id) for row in rows if row.tag_id is not None]
    if not tag_ids:
        return []
    for tag_id, name in db.query(Tag.id, Tag.name).filter(Tag.id.in_(tag_ids)).all():
        name = str(name or "").strip()
        if name:
            counts[name] = counts.get(name, 0) + 1
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [name for name, _ in ordered[:_RULE_TOP_N]]


def _top_type_names(db: Session, doc_ids: list[int]) -> list[str]:
    """Most frequent document-type names attached to the given docs."""
    if not doc_ids:
        return []
    counts: dict[str, int] = {}
    rows = (
        db.query(Document.document_type_id)
        .filter(Document.id.in_(doc_ids))
        .all()
    )
    type_ids = [int(row.document_type_id) for row in rows if row.document_type_id is not None]
    if not type_ids:
        return []
    for type_id, name in db.query(DocumentType.id, DocumentType.name).filter(
        DocumentType.id.in_(type_ids)
    ).all():
        name = str(name or "").strip()
        if name:
            counts[name] = counts.get(name, 0) + 1
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [name for name, _ in ordered[:_RULE_TOP_N]]


def learn_correspondent_rules(db: Session, doc_id: int) -> dict[str, Any]:
    """Aggregate confirmed field patterns for the document's correspondent.

    Only documents the reviewer already confirmed (an ``apply_to_document:*`` or
    ``mark_reviewed`` audit entry) count as a reliable signal. Returns an empty
    dict when the document has no correspondent, or when there are no reviewed
    documents to learn from — so callers can skip the prompt prefix.
    """
    doc = db.get(Document, doc_id)
    if doc is None or doc.correspondent_id is None:
        return {}
    reviewed_ids = _reviewed_doc_ids(db, int(doc.correspondent_id))
    top_tags = _top_tag_names(db, reviewed_ids)
    top_types = _top_type_names(db, reviewed_ids)
    if not top_tags and not top_types:
        return {}
    return {
        "correspondent_id": int(doc.correspondent_id),
        "top_tags": top_tags,
        "top_document_types": top_types,
    }


def build_learned_rules_instruction(rules: dict[str, Any] | None) -> str:
    """Instruction telling the model the confirmed patterns of a correspondent.

    These are values a reviewer already accepted for the same correspondent, so
    they are a strong prior for tags and document type. Returns an empty string
    when there is nothing to convey.
    """
    if not rules:
        return ""
    parts: list[str] = []
    top_tags = rules.get("top_tags") or []
    top_types = rules.get("top_document_types") or []
    if top_tags:
        parts.append("Typical tags: " + ", ".join(str(t) for t in top_tags))
    if top_types:
        parts.append("Typical document types: " + ", ".join(str(t) for t in top_types))
    if not parts:
        return ""
    return (
        "The document's correspondent has these confirmed patterns from previously "
        "reviewed documents. Use them as a strong prior for tags and documentType, "
        "but always prefer what the document itself states:\n" + "; ".join(parts)
    )
