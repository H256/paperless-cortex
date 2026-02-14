from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Document, DocumentSuggestion
from app.services.json_utils import parse_json_object
from app.services.suggestions import normalize_suggestions_payload


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def should_skip_doc(doc: Document) -> bool:
    return bool(doc.deleted_at and str(doc.deleted_at).startswith("DELETED in Paperless"))


def parse_suggestion_payload(row: DocumentSuggestion, tags: list[str]) -> dict[str, object]:
    parsed = parse_json_object(row.payload)
    if not parsed:
        return {"raw": row.payload}
    return normalize_suggestions_payload(parsed, tags)


def load_suggestions_map(
    db: Session, doc_id: int, tags: list[str], source: str | None = None
) -> dict[str, object]:
    query = db.query(DocumentSuggestion).filter(DocumentSuggestion.doc_id == doc_id)
    if source:
        query = query.filter(DocumentSuggestion.source == source)
    rows = query.order_by(DocumentSuggestion.source.asc()).all()
    return {row.source: parse_suggestion_payload(row, tags) for row in rows}
