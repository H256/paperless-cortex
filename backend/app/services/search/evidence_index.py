from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from app.models import DocumentPageAnchor

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def extract_pdf_page_anchors(pdf_bytes: bytes) -> list[dict[str, Any]]:
    import fitz  # pymupdf

    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    rows: list[dict[str, Any]] = []
    for page_index in range(document.page_count):
        page = document[page_index]
        words = page.get_text("words", sort=True) or []
        anchors: list[dict[str, Any]] = []
        for raw in words:
            if len(raw) < 5:
                continue
            x0, y0, x1, y1 = float(raw[0]), float(raw[1]), float(raw[2]), float(raw[3])
            if not (x1 > x0 and y1 > y0):
                continue
            text = str(raw[4] or "").strip()
            if not text:
                continue
            anchors.append({"text": text, "bbox": [x0, y0, x1, y1]})
        rows.append(
            {
                "page": page_index + 1,
                "anchors": anchors,
                "token_count": len(anchors),
                "status": "ok" if anchors else "no_text_layer",
                "error": None,
            }
        )
    return rows


def upsert_page_anchors(
    db: Session,
    *,
    doc_id: int,
    source: str,
    rows: list[dict[str, Any]],
) -> None:
    now = datetime.now(UTC).isoformat()
    for row in rows:
        page = int(row.get("page") or 0)
        if page <= 0:
            continue
        existing = db.get(DocumentPageAnchor, (int(doc_id), page, source))
        if not existing:
            existing = DocumentPageAnchor(doc_id=int(doc_id), page=page, source=source)
            existing.created_at = now
            db.add(existing)
        anchors = row.get("anchors")
        if isinstance(anchors, list):
            existing.anchors_json = json.dumps(anchors, ensure_ascii=False)
        else:
            existing.anchors_json = "[]"
        existing.token_count = int(row.get("token_count") or 0)
        existing.status = str(row.get("status") or "ok")
        error = row.get("error")
        existing.error = str(error)[:1000] if error else None
        existing.processed_at = now
    db.commit()
