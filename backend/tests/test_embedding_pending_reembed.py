"""Regression tests for AUDIT DOC-003: embedding failure must not leave a doc
with no vector points while the skip guard still treats it as embedded.

The fix persists a ``pending_reembed`` flag on ``DocumentEmbedding`` before the
non-transactional point deletion, so a mid-run ``embed_text`` failure keeps the
doc flagged and the next run re-embeds it instead of skipping it.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import load_settings
from app.models import Document, DocumentEmbedding
from app.services.documents.embedding_operations import ingest_embeddings_for_documents
from app.services.documents.sync_operations import embed_documents


def _hash(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def _verify_db() -> Any:
    import os

    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    return Session(engine)


def test_embed_documents_sets_pending_reembed_on_failure(
    session_factory: Any, monkeypatch: Any
) -> None:
    import app.services.documents.sync_operations as sync_operations

    monkeypatch.setenv("EMBEDDING_MODEL", "test-model")
    settings = load_settings()
    monkeypatch.setattr(sync_operations, "ensure_embedding_collection", lambda *_a, **_k: None)
    monkeypatch.setattr(
        sync_operations, "collect_page_texts", lambda *_a, **_k: (None, [], [])
    )
    monkeypatch.setattr(
        sync_operations, "delete_points_for_doc", lambda *_a, **_k: None
    )
    monkeypatch.setattr(
        sync_operations, "chunk_document_with_pages", lambda *_a, **_k: [{"text": "c"}]
    )
    monkeypatch.setattr(sync_operations, "embed_text", lambda *_a, **_k: [0.1, 0.2])
    monkeypatch.setattr(sync_operations, "average_vectors", lambda *_a, **_k: [0.15])
    monkeypatch.setattr(
        sync_operations, "record_source_chunk_count", lambda *_a, **_k: None
    )

    with session_factory() as db:
        db.add(Document(id=901, title="Doc", content="some content"))
        # Pre-embedded: hash matches, so the skip guard WOULD fire without the flag.
        db.add(
            DocumentEmbedding(
                doc_id=901,
                content_hash=_hash("some content"),
                embedding_model="test-model",
                chunk_count=2,
            )
        )
        db.commit()

        def _raise(_s: Any, _t: str) -> list[float]:
            raise RuntimeError("embedding boom")

        monkeypatch.setattr(sync_operations, "embed_text", _raise)
        with pytest.raises(RuntimeError, match="embedding boom"):
            # force_embed=True models a re-embed (content changed / manual force);
            # the new embed_text fails mid-doc, leaving the doc flagged.
            embed_documents(db, settings, [db.get(Document, 901)], force_embed=True)

    with _verify_db() as vdb:
        row = vdb.get(DocumentEmbedding, 901)
        assert row is not None
        assert row.pending_reembed is True


def test_embed_documents_reembeds_flagged_doc_on_next_run(
    session_factory: Any, monkeypatch: Any
) -> None:
    """A doc left flagged by a failed run must be re-embedded (not skipped) on
    the next run, and the flag cleared once the upsert succeeds."""
    import app.services.documents.sync_operations as sync_operations

    monkeypatch.setenv("EMBEDDING_MODEL", "test-model")
    settings = load_settings()
    monkeypatch.setattr(sync_operations, "ensure_embedding_collection", lambda *_a, **_k: None)
    monkeypatch.setattr(
        sync_operations, "collect_page_texts", lambda *_a, **_k: (None, [], [])
    )
    monkeypatch.setattr(
        sync_operations, "delete_points_for_doc", lambda *_a, **_k: None
    )
    monkeypatch.setattr(
        sync_operations, "chunk_document_with_pages", lambda *_a, **_k: [{"text": "c"}]
    )
    monkeypatch.setattr(sync_operations, "embed_text", lambda *_a, **_k: [0.1, 0.2])
    monkeypatch.setattr(sync_operations, "average_vectors", lambda *_a, **_k: [0.15])
    monkeypatch.setattr(
        sync_operations, "record_source_chunk_count", lambda *_a, **_k: None
    )

    upserted: list[Any] = []
    monkeypatch.setattr(
        sync_operations, "upsert_points", lambda _s, pts: upserted.extend(pts)
    )

    with session_factory() as db:
        db.add(Document(id=902, title="Doc", content="some content"))
        # Simulate the aftermath of a failed run: hash matches but flag is set.
        db.add(
            DocumentEmbedding(
                doc_id=902,
                content_hash=_hash("some content"),
                embedding_model="test-model",
                chunk_count=2,
                pending_reembed=True,
            )
        )
        db.commit()
        embedded = embed_documents(db, settings, [db.get(Document, 902)])

    assert embedded == 1
    assert upserted, "flagged doc must be re-embedded, not skipped"
    with _verify_db() as vdb:
        row = vdb.get(DocumentEmbedding, 902)
        assert row is not None
        assert row.pending_reembed is False


def test_ingest_embeddings_sets_pending_reembed_on_failure(
    session_factory: Any, monkeypatch: Any
) -> None:
    monkeypatch.setenv("EMBEDDING_MODEL", "test-model")
    settings = load_settings()

    with session_factory() as db:
        db.add(Document(id=903, title="Doc", content="some content"))
        db.add(
            DocumentEmbedding(
                doc_id=903,
                content_hash=_hash("some content"),
                embedding_model="test-model",
                chunk_count=2,
            )
        )
        db.commit()
        doc = db.get(Document, 903)

        def _raise(_s: Any, _t: str) -> list[float]:
            raise RuntimeError("embedding boom")

        with pytest.raises(RuntimeError, match="embedding boom"):
            ingest_embeddings_for_documents(
                db=db,
                settings=settings,
                documents=[doc],
                force=True,
                ensure_embedding_collection_fn=lambda *_a, **_k: None,
                collect_page_texts_fn=lambda *_a, **_k: ([], [], []),
                chunk_document_with_pages_fn=lambda *_a, **_k: [{"text": "c"}],
                delete_points_for_doc_fn=lambda *_a, **_k: None,
                embed_text_fn=_raise,
                make_point_id_fn=lambda *a, **k: 1,
                make_doc_point_id_fn=lambda *a, **k: 2,
                upsert_points_fn=lambda *_a, **_k: None,
                record_source_chunk_count_fn=lambda *_a, **_k: None,
            )

    with _verify_db() as vdb:
        row = vdb.get(DocumentEmbedding, 903)
        assert row is not None
        assert row.pending_reembed is True
