"""Global duplicate detection: per-document scan, grouping and ignore handling."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app.models import Document, DocumentDuplicatePair, DocumentPageText
from app.services.documents.duplicate_scoring import (
    LEVEL_CHECK,
    LEVEL_LIKELY,
    LEVEL_VERY_LIKELY,
    LEVELS,
    DocFingerprint,
    cluster_pairs,
    fingerprint_from_text,
    score_pair,
)
from app.services.runtime.time_utils import utc_now_iso
from app.services.search.similarity import fetch_doc_point_vector, search_similar_doc_points

if TYPE_CHECKING:
    from collections.abc import Callable

    from app.config import Settings

logger = logging.getLogger(__name__)

DEFAULT_EMBEDDING_THRESHOLD = 0.85
DEFAULT_MIN_SCORE = 0.60
DEFAULT_TOP_K = 10

_LEVEL_FLOOR = {LEVEL_VERY_LIKELY: 0.90, LEVEL_LIKELY: 0.78, LEVEL_CHECK: 0.0}


def _ordered(doc_id: int, other_id: int) -> tuple[int, int]:
    return (doc_id, other_id) if doc_id < other_id else (other_id, doc_id)


def _document_text(db: Session, doc: Document) -> str:
    if doc.content and doc.content.strip():
        return doc.content
    rows = (
        db.query(DocumentPageText)
        .filter(DocumentPageText.doc_id == int(doc.id))
        .order_by(DocumentPageText.source, DocumentPageText.page)
        .all()
    )
    if not rows:
        return ""
    first_source = rows[0].source
    return "\n".join(
        str(row.clean_text or row.text or "") for row in rows if row.source == first_source
    )


def _fingerprint(db: Session, doc: Document) -> DocFingerprint:
    return fingerprint_from_text(
        int(doc.id),
        _document_text(db, doc),
        correspondent_id=doc.correspondent_id,
        document_type_id=doc.document_type_id,
        document_date=doc.document_date,
        page_count=doc.page_count,
    )


def scan_document_duplicates(
    settings: Settings,
    db: Session,
    doc_id: int,
    *,
    is_cancel_requested_fn: Callable[[Settings], bool],
    embedding_threshold: float = DEFAULT_EMBEDDING_THRESHOLD,
    min_score: float = DEFAULT_MIN_SCORE,
    top_k: int = DEFAULT_TOP_K,
) -> int:
    """Refresh all non-ignored duplicate pairs touching ``doc_id``; return pairs stored."""
    if is_cancel_requested_fn(settings):
        logger.info("Worker cancel requested; abort duplicate scan doc=%s", doc_id)
        return 0
    doc = db.get(Document, int(doc_id))
    vector = fetch_doc_point_vector(settings, int(doc_id)) if doc else None
    if doc is None or not vector:
        return 0

    matches = search_similar_doc_points(
        settings, vector, top_k=top_k + 1, min_score=embedding_threshold
    )
    embedding_by_doc = {
        int(m["doc_id"]): float(m["score"]) for m in matches if int(m["doc_id"]) != int(doc_id)
    }
    candidates = {
        int(row.id): row
        for row in db.query(Document).filter(Document.id.in_(list(embedding_by_doc))).all()
    }
    base = _fingerprint(db, doc)

    scored: list[tuple[int, Any]] = []
    for other_id, embedding_score in embedding_by_doc.items():
        other = candidates.get(other_id)
        if other is None or other.deleted_at:
            continue
        result = score_pair(base, _fingerprint(db, other), embedding_score=embedding_score)
        if result.score >= min_score:
            scored.append((other_id, result))

    existing = {
        (row.doc_a_id, row.doc_b_id): row
        for row in db.query(DocumentDuplicatePair).filter(
            or_(
                DocumentDuplicatePair.doc_a_id == int(doc_id),
                DocumentDuplicatePair.doc_b_id == int(doc_id),
            )
        )
    }
    now = utc_now_iso()
    kept: set[tuple[int, int]] = set()
    for other_id, result in scored:
        key = _ordered(int(doc_id), other_id)
        kept.add(key)
        row = existing.get(key) or DocumentDuplicatePair(doc_a_id=key[0], doc_b_id=key[1])
        row.score = result.score
        row.level = result.level
        row.embedding_score = result.embedding_score
        row.text_score = result.text_score
        row.keys_score = result.keys_score
        row.meta_score = result.meta_score
        row.signals_json = json.dumps(result.signals, ensure_ascii=False)
        row.scanned_at = now
        if key not in existing:
            row.ignored = False
            db.add(row)
    for key, row in existing.items():
        if key not in kept and not row.ignored:
            db.delete(row)
    db.commit()
    return len(scored)


def _doc_summary(doc: Document) -> dict[str, Any]:
    return {
        "id": int(doc.id),
        "title": doc.title,
        "document_date": doc.document_date,
        "created": doc.created,
        "correspondent_id": doc.correspondent_id,
        "correspondent_name": doc.correspondent.name if doc.correspondent else None,
        "document_type_id": doc.document_type_id,
        "page_count": doc.page_count,
        "original_file_name": doc.original_file_name,
    }


def _pair_payload(row: DocumentDuplicatePair) -> dict[str, Any]:
    try:
        signals = json.loads(row.signals_json) if row.signals_json else {}
    except (TypeError, ValueError):
        signals = {}
    return {
        "doc_a_id": int(row.doc_a_id),
        "doc_b_id": int(row.doc_b_id),
        "score": float(row.score),
        "level": row.level,
        "embedding_score": row.embedding_score,
        "text_score": row.text_score,
        "keys_score": row.keys_score,
        "meta_score": row.meta_score,
        "signals": signals,
        "ignored": bool(row.ignored),
        "ignored_at": row.ignored_at,
        "scanned_at": row.scanned_at,
    }


def _load_documents(db: Session, doc_ids: set[int]) -> dict[int, Document]:
    if not doc_ids:
        return {}
    rows = (
        db.query(Document)
        .options(selectinload(Document.correspondent))
        .filter(Document.id.in_(doc_ids))
        .all()
    )
    return {int(row.id): row for row in rows}


def list_duplicate_groups(
    db: Session,
    *,
    min_level: str = LEVEL_CHECK,
    limit: int = 200,
) -> dict[str, Any]:
    floor = _LEVEL_FLOOR.get(min_level, 0.0)
    rows = (
        db.query(DocumentDuplicatePair)
        .filter(DocumentDuplicatePair.ignored.is_(False), DocumentDuplicatePair.score >= floor)
        .order_by(DocumentDuplicatePair.score.desc())
        .all()
    )
    groups = cluster_pairs([(int(r.doc_a_id), int(r.doc_b_id)) for r in rows])
    group_by_doc = {doc_id: idx for idx, members in enumerate(groups) for doc_id in members}
    pairs_by_group: dict[int, list[DocumentDuplicatePair]] = {}
    for row in rows:
        pairs_by_group.setdefault(group_by_doc[int(row.doc_a_id)], []).append(row)

    docs = _load_documents(db, {doc_id for members in groups for doc_id in members})
    payload_groups: list[dict[str, Any]] = []
    for idx, members in enumerate(groups):
        pairs = pairs_by_group.get(idx, [])
        best = max((float(p.score) for p in pairs), default=0.0)
        payload_groups.append(
            {
                "group_id": min(members),
                "doc_ids": members,
                "best_score": best,
                "level": _best_level(pairs),
                "documents": [_doc_summary(docs[d]) for d in members if d in docs],
                "pairs": [_pair_payload(p) for p in pairs],
            }
        )
    payload_groups.sort(key=lambda g: g["best_score"], reverse=True)
    return {
        "total": len(payload_groups),
        "groups": payload_groups[: max(1, limit)],
    }


def _best_level(pairs: list[DocumentDuplicatePair]) -> str:
    for level in LEVELS:
        if any(p.level == level for p in pairs):
            return level
    return LEVEL_CHECK


def list_ignored_pairs(db: Session) -> dict[str, Any]:
    rows = (
        db.query(DocumentDuplicatePair)
        .filter(DocumentDuplicatePair.ignored.is_(True))
        .order_by(DocumentDuplicatePair.ignored_at.desc())
        .all()
    )
    docs = _load_documents(
        db, {int(r.doc_a_id) for r in rows} | {int(r.doc_b_id) for r in rows}
    )
    items = []
    for row in rows:
        item = _pair_payload(row)
        item["documents"] = [
            _doc_summary(docs[d]) for d in (int(row.doc_a_id), int(row.doc_b_id)) if d in docs
        ]
        items.append(item)
    return {"total": len(items), "pairs": items}


def set_pair_ignored(db: Session, doc_a_id: int, doc_b_id: int, *, ignored: bool) -> bool:
    """Flip the ignore flag. Returns False when the pair is unknown."""
    a, b = _ordered(int(doc_a_id), int(doc_b_id))
    row = db.get(DocumentDuplicatePair, (a, b))
    if row is None:
        return False
    row.ignored = ignored
    row.ignored_at = utc_now_iso() if ignored else None
    db.commit()
    return True
