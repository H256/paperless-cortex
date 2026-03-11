from __future__ import annotations

import os
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Correspondent, Document, DocumentEmbedding, SyncState


def _insert_document(
    doc_id: int,
    title: str,
    *,
    correspondent_id: int | None = None,
    content: str | None = "doc content",
) -> None:
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(
            Document(
                id=doc_id,
                title=title,
                content=content,
                correspondent_id=correspondent_id,
                created="2026-03-11T10:00:00+00:00",
                modified="2026-03-11T10:00:00+00:00",
            )
        )
        db.commit()


def _insert_correspondent(correspondent_id: int, name: str) -> None:
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(Correspondent(id=correspondent_id, name=name))
        db.commit()


def _insert_sync_state(
    key: str,
    *,
    status: str = "running",
    processed: int = 0,
    total: int = 0,
    started_at: str | None = None,
    last_synced_at: str | None = None,
    cancel_requested: bool = False,
) -> None:
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(
            SyncState(
                key=key,
                status=status,
                processed=processed,
                total=total,
                started_at=started_at,
                last_synced_at=last_synced_at,
                cancel_requested=cancel_requested,
            )
        )
        db.commit()


def test_embeddings_ingest_queues_documents(api_client: Any, monkeypatch: Any) -> None:
    from app.routes import embeddings

    _insert_document(701, "Queue Doc A")
    _insert_document(702, "Queue Doc B")
    monkeypatch.setenv("QUEUE_ENABLED", "1")
    monkeypatch.setenv("ENABLE_VISION_OCR", "0")

    queued: list[dict[str, Any]] = []

    def _enqueue_task(_settings: Any, payload: dict[str, Any]) -> None:
        queued.append(dict(payload))

    monkeypatch.setattr(embeddings, "enqueue_task", _enqueue_task)

    response = api_client.post("/embeddings/ingest")
    assert response.status_code == 200
    payload = response.json()
    assert payload["queued"] == 2
    assert payload["ingested"] == 0
    assert payload["documents_embedded"] == 0
    assert queued == [
        {"doc_id": 701, "task": "embeddings_paperless"},
        {"doc_id": 702, "task": "embeddings_paperless"},
    ]


def test_embeddings_status_reports_queue_progress(api_client: Any, monkeypatch: Any) -> None:
    from app.routes import embeddings

    monkeypatch.setenv("QUEUE_ENABLED", "1")
    _insert_sync_state(
        "embeddings",
        status="running",
        processed=3,
        total=10,
        started_at="2026-03-11T10:00:00+00:00",
        last_synced_at="2026-03-11T10:01:00+00:00",
    )
    monkeypatch.setattr(
        embeddings,
        "queue_stats",
        lambda _settings: {"length": 4, "total": 10, "in_progress": 1, "done": 3},
    )

    response = api_client.get("/embeddings/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "running"
    assert payload["processed"] == 3
    assert payload["total"] == 10
    assert payload["started_at"] == "2026-03-11T10:00:00+00:00"
    assert payload["last_synced_at"] == "2026-03-11T10:01:00+00:00"
    assert payload["cancel_requested"] is False


def test_embeddings_cancel_marks_state(api_client: Any) -> None:
    _insert_sync_state("embeddings", status="running", processed=1, total=2)

    response = api_client.post("/embeddings/cancel")
    assert response.status_code == 200
    assert response.json()["status"] == "cancelling"

    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        state = db.get(SyncState, "embeddings")
        assert state is not None
        assert state.cancel_requested is True


def test_embeddings_search_includes_local_document_context(
    api_client: Any, monkeypatch: Any
) -> None:
    from app.routes import embeddings

    _insert_correspondent(81, "Acme Corp")
    _insert_document(801, "Searchable Doc", correspondent_id=81)
    monkeypatch.setattr(embeddings, "embed_text", lambda _settings, _text: [0.1, 0.2, 0.3])
    monkeypatch.setattr(
        embeddings,
        "search_points",
        lambda _settings, _vector, limit, filter_payload: {
            "result": [
                {
                    "score": 0.92,
                    "payload": {
                        "doc_id": 801,
                        "page": 2,
                        "text": "Invoice amount due from Acme Corp",
                        "source": "vision_ocr",
                        "quality_score": 88,
                        "bbox": [0.1, 0.2, 0.3, 0.4],
                    },
                }
            ]
        },
    )

    response = api_client.get(
        "/embeddings/search",
        params={"q": "invoice amount", "top_k": 5, "include_doc": True, "source": "vision_ocr"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "invoice amount"
    assert payload["top_k"] == 5
    assert len(payload["matches"]) == 1
    match = payload["matches"][0]
    assert match["doc_id"] == 801
    assert match["page"] == 2
    assert match["source"] == "vision_ocr"
    assert match["quality_score"] == 88
    assert match["document"]["id"] == 801
    assert match["document"]["title"] == "Searchable Doc"
    assert match["document"]["correspondent_name"] == "Acme Corp"


def test_embeddings_search_filters_low_quality_matches(api_client: Any, monkeypatch: Any) -> None:
    from app.routes import embeddings

    monkeypatch.setattr(embeddings, "embed_text", lambda _settings, _text: [0.1, 0.2, 0.3])
    monkeypatch.setattr(
        embeddings,
        "search_points",
        lambda _settings, _vector, limit, filter_payload: {
            "result": [
                {
                    "score": 0.9,
                    "payload": {
                        "doc_id": 901,
                        "page": 1,
                        "text": "low quality hit",
                        "source": "vision_ocr",
                        "quality_score": 40,
                    },
                },
                {
                    "score": 0.7,
                    "payload": {
                        "doc_id": 902,
                        "page": 1,
                        "text": "good quality hit",
                        "source": "vision_ocr",
                        "quality_score": 85,
                    },
                },
            ]
        },
    )

    response = api_client.get(
        "/embeddings/search",
        params={"q": "quality", "top_k": 5, "source": "vision_ocr", "min_quality": 80},
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["matches"]) == 1
    assert payload["matches"][0]["doc_id"] == 902


def test_embeddings_ingest_non_queue_embeds_document(api_client: Any, monkeypatch: Any) -> None:
    from app.routes import embeddings

    _insert_document(950, "Embed Now Doc", content="doc content for embedding")
    monkeypatch.setenv("QUEUE_ENABLED", "0")
    monkeypatch.setenv("EMBEDDING_MODEL", "test-embed")
    monkeypatch.setattr(embeddings, "ensure_embedding_collection", lambda _settings: None)
    monkeypatch.setattr(embeddings, "collect_page_texts", lambda *_args, **_kwargs: ([], [], []))
    monkeypatch.setattr(
        embeddings,
        "chunk_document_with_pages",
        lambda _settings, content, pages: [
            {"text": "chunk one", "page": 1, "source": "paperless_ocr", "quality_score": 100}
        ],
    )
    monkeypatch.setattr(embeddings, "delete_points_for_doc", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(embeddings, "embed_text", lambda _settings, _text: [0.1, 0.2, 0.3])

    captured_points: list[dict[str, Any]] = []

    def _upsert_points(_settings: Any, points: list[dict[str, Any]]) -> None:
        captured_points.extend(points)

    monkeypatch.setattr(embeddings, "upsert_points", _upsert_points)

    response = api_client.post("/embeddings/ingest", params={"doc_id": 950})
    assert response.status_code == 200
    payload = response.json()
    assert payload["documents_embedded"] == 1
    assert payload["ingested"] == 2
    assert len(captured_points) == 2

    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        row = db.get(DocumentEmbedding, 950)
        assert row is not None
        assert row.chunk_count == 1
        assert row.embedding_model == "test-embed"
