from __future__ import annotations

import os
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import load_settings
from app.models import Document
from app.services.pipeline import worker_document_tasks


def _settings() -> Any:
    return load_settings()


def test_purge_opposite_source_both_mode_keeps_opposite(monkeypatch: Any) -> None:
    calls: list[tuple[int, str | None]] = []
    monkeypatch.setattr(
        worker_document_tasks,
        "delete_points_for_doc",
        lambda settings, doc_id, source=None: calls.append((doc_id, source)),
    )
    # "both" mode: opposite source is populated by a separate task, so no purge.
    worker_document_tasks._purge_opposite_source(_settings(), 10, "paperless", "both")
    assert calls == []


def test_purge_opposite_source_single_mode_purges_opposite(monkeypatch: Any) -> None:
    calls: list[tuple[int, str | None]] = []
    monkeypatch.setattr(
        worker_document_tasks,
        "delete_points_for_doc",
        lambda settings, doc_id, source=None: calls.append((doc_id, source)),
    )
    # Single-source paperless: vision points must be purged.
    worker_document_tasks._purge_opposite_source(_settings(), 10, "paperless", "paperless")
    assert calls == [(10, "vision")]


def test_purge_opposite_source_vision_purges_paperless(monkeypatch: Any) -> None:
    calls: list[tuple[int, str | None]] = []
    monkeypatch.setattr(
        worker_document_tasks,
        "delete_points_for_doc",
        lambda settings, doc_id, source=None: calls.append((doc_id, source)),
    )
    worker_document_tasks._purge_opposite_source(_settings(), 10, "vision", "vision")
    assert calls == [(10, "paperless")]


def test_purge_opposite_source_auto_mode_defaults_to_purge(monkeypatch: Any) -> None:
    calls: list[tuple[int, str | None]] = []
    monkeypatch.setattr(
        worker_document_tasks,
        "delete_points_for_doc",
        lambda settings, doc_id, source=None: calls.append((doc_id, source)),
    )
    # No explicit mode (e.g. legacy task payload) behaves as single-source: purge.
    worker_document_tasks._purge_opposite_source(_settings(), 10, "paperless", "")
    assert calls == [(10, "vision")]


def test_inline_ingest_purges_opposite_source(api_client: Any, monkeypatch: Any) -> None:
    from app.routes import embeddings

    _insert_document(960, "Switch Purge Doc", content="content for switch purge")
    monkeypatch.setenv("QUEUE_ENABLED", "0")
    monkeypatch.setenv("EMBEDDING_MODEL", "test-embed")
    monkeypatch.setattr(embeddings, "ensure_embedding_collection", lambda _settings: None)
    monkeypatch.setattr(embeddings, "collect_page_texts", lambda *_a, **_k: ([], [], []))
    monkeypatch.setattr(
        embeddings,
        "chunk_document_with_pages",
        lambda _settings, content, pages: [
            {"text": "chunk one", "page": 1, "source": "paperless_ocr", "quality_score": 100}
        ],
    )
    delete_calls: list[str | None] = []
    monkeypatch.setattr(
        embeddings,
        "delete_points_for_doc",
        lambda _settings, _doc_id, source=None: delete_calls.append(source),
    )
    monkeypatch.setattr(embeddings, "embed_text", lambda _settings, _text: [0.1, 0.2, 0.3])
    monkeypatch.setattr(embeddings, "upsert_points", lambda _settings, _points: None)

    response = api_client.post("/embeddings/ingest", params={"doc_id": 960})
    assert response.status_code == 200
    # Inline path consolidates all chunks under one source; the opposite source's
    # points must be purged so a source switch does not double-match.
    assert "vision" in delete_calls
    assert "paperless" in delete_calls


def _insert_document(doc_id: int, title: str, *, content: str | None = "content") -> None:
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(
            Document(
                id=doc_id,
                title=title,
                content=content,
                created="2026-03-11T10:00:00+00:00",
                modified="2026-03-11T10:00:00+00:00",
            )
        )
        db.commit()
