from __future__ import annotations

from typing import Any

from app.config import load_settings
from app.models import Document, DocumentPageText
from app.services.documents.page_text_store import (
    RECLEAN_STREAM_BATCH,
    reclean_page_texts,
)
from app.services.documents.text_cleaning import clean_ocr_text, estimate_tokens


def _seed_page_texts(db: Any, doc_id: int, count: int) -> None:
    db.add(Document(id=doc_id, title=f"doc {doc_id}"))
    db.flush()
    for page in range(1, count + 1):
        db.add(
            DocumentPageText(
                doc_id=doc_id,
                page=page,
                source="paperless",
                text=f"page {page} body text",
                raw_text=None,
                clean_text=None,
                token_estimate_raw=None,
                token_estimate_clean=None,
                quality_score=None,
                cleaned_at=None,
                processed_at=None,
            )
        )
    db.commit()


def test_reclean_streams_and_persists_beyond_one_batch(session_factory: Any) -> None:
    """Reclean must process the whole table in bounded chunks and persist every row.

    Seeds more rows than RECLEAN_STREAM_BATCH so the loop crosses multiple
    mid-iteration commits (the regression #212 fixes: no full-table
    materialization, but all rows still cleaned and committed).
    """
    settings = load_settings()
    total = RECLEAN_STREAM_BATCH * 2 + 50
    with session_factory() as db:
        _seed_page_texts(db, 1, total)
        _seed_page_texts(db, 2, 3)

        result = reclean_page_texts(db, settings, doc_id=1, source=None, clear_first=False)

        assert result["processed"] == total
        # Every row must be cleaned and persisted across the streamed batches.
        rows = (
            db.query(DocumentPageText)
            .filter(DocumentPageText.doc_id == 1)
            .all()
        )
        assert len(rows) == total
        for row in rows:
            raw = row.raw_text if row.raw_text is not None else (row.text or "")
            expected_clean = clean_ocr_text(raw)
            assert row.clean_text == expected_clean
            assert row.token_estimate_clean == estimate_tokens(expected_clean)
            assert row.token_estimate_raw == estimate_tokens(raw)
            assert row.cleaned_at is not None
            assert row.processed_at is not None


def test_reclean_doc_id_filter_streams_only_matching(session_factory: Any) -> None:
    """doc_id filtering must hold while streaming; other docs stay untouched."""
    settings = load_settings()
    with session_factory() as db:
        _seed_page_texts(db, 1, RECLEAN_STREAM_BATCH + 10)
        _seed_page_texts(db, 2, 5)

        result = reclean_page_texts(db, settings, doc_id=2, source=None, clear_first=False)

        assert result["processed"] == 5
        # Doc 2 rows cleaned; doc 1 rows untouched (clean_text still None).
        doc2 = db.query(DocumentPageText).filter(DocumentPageText.doc_id == 2).all()
        assert all(r.clean_text is not None for r in doc2)
        doc1 = db.query(DocumentPageText).filter(DocumentPageText.doc_id == 1).all()
        assert all(r.clean_text is None for r in doc1)


def test_reclean_empty_table_returns_zero(session_factory: Any) -> None:
    settings = load_settings()
    with session_factory() as db:
        result = reclean_page_texts(db, settings, doc_id=999, source=None, clear_first=False)
        assert result == {"processed": 0, "updated": 0}
