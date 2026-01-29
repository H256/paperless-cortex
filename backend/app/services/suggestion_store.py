from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import delete
from sqlalchemy.orm import Session
import logging

from app.models import DocumentSuggestion, SuggestionAudit

logger = logging.getLogger(__name__)


def upsert_suggestion(
    db: Session,
    doc_id: int,
    source: str,
    payload: str,
) -> None:
    db.execute(
        delete(DocumentSuggestion).where(
            DocumentSuggestion.doc_id == doc_id,
            DocumentSuggestion.source == source,
        )
    )
    created_at = datetime.now(timezone.utc).isoformat()
    db.add(
        DocumentSuggestion(
            doc_id=doc_id,
            source=source,
            payload=payload,
            created_at=created_at,
        )
    )
    db.commit()
    logger.info("Stored suggestions doc=%s source=%s", doc_id, source)


def update_suggestion_field(
    db: Session,
    doc_id: int,
    source: str,
    field: str,
    value: object,
) -> dict[str, object] | None:
    row = (
        db.query(DocumentSuggestion)
        .filter(DocumentSuggestion.doc_id == doc_id, DocumentSuggestion.source == source)
        .one_or_none()
    )
    if not row:
        return None
    try:
        payload = __import__("json").loads(row.payload)
    except Exception:
        payload = {}
    old_value = payload.get(field) if isinstance(payload, dict) else None
    if isinstance(payload, dict) and "parsed" in payload and isinstance(payload["parsed"], dict):
        payload["parsed"][field] = value
    if isinstance(payload, dict):
        payload[field] = value
    row.payload = __import__("json").dumps(payload, ensure_ascii=False)
    db.commit()
    logger.info("Updated suggestion doc=%s source=%s field=%s", doc_id, source, field)
    audit = SuggestionAudit(
        doc_id=doc_id,
        action="field_override",
        source=source,
        field=field,
        old_value=__import__("json").dumps(old_value, ensure_ascii=False) if old_value is not None else None,
        new_value=__import__("json").dumps(value, ensure_ascii=False) if value is not None else None,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    db.add(audit)
    db.commit()
    return payload


def audit_suggestion_run(
    db: Session,
    doc_id: int,
    source: str,
    action: str,
) -> None:
    audit = SuggestionAudit(
        doc_id=doc_id,
        action=action,
        source=source,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    db.add(audit)
    db.commit()
