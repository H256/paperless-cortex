from __future__ import annotations

from typing import Any

from app.config import load_settings
from app.models import Document, DocumentEmbedding
from app.services.search.vector_integrity import audit_missing_vector_chunks


def test_audit_missing_vector_chunks_reports_fully_missing_docs(
    session_factory: Any,
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("VECTOR_STORE_PROVIDER", "weaviate")
    monkeypatch.setenv("WEAVIATE_HTTP_HOST", "weaviate")
    settings = load_settings()

    with session_factory() as db:
        db.add(Document(id=67, title="Missing Vision Doc"))
        db.add(
            DocumentEmbedding(
                doc_id=67,
                embedding_source="vision",
                chunk_count=4,
                embedded_at="2026-03-14T09:51:13.631637+00:00",
            )
        )
        db.commit()

        def _retrieve_points(
            _settings: Any,
            ids: list[int],
            *,
            with_vector: bool = True,
            with_payload: bool = False,
        ) -> dict[str, object]:
            del _settings, ids, with_vector, with_payload
            return {"result": []}

        payload = audit_missing_vector_chunks(
            settings,
            db,
            limit=20,
            retrieve_points_fn=_retrieve_points,
        )

    assert payload["provider"] == "weaviate"
    assert payload["scanned_docs"] == 1
    assert payload["affected_docs"] == 1
    assert payload["fully_missing_docs"] == 1
    assert payload["partial_missing_docs"] == 0
    assert payload["items"] == [
        {
            "doc_id": 67,
            "title": "Missing Vision Doc",
            "embedding_source": "vision",
            "chunk_count": 4,
            "expected_vectors": 4,
            "found_vectors": 0,
            "fully_missing": True,
            "embedded_at": "2026-03-14T09:51:13.631637+00:00",
        }
    ]


def test_audit_missing_vector_chunks_reports_partial_missing_docs(
    session_factory: Any,
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("VECTOR_STORE_PROVIDER", "weaviate")
    monkeypatch.setenv("WEAVIATE_HTTP_HOST", "weaviate")
    settings = load_settings()

    with session_factory() as db:
        db.add(Document(id=68, title="Partial Vision Doc"))
        db.add(
            DocumentEmbedding(
                doc_id=68,
                embedding_source="vision",
                chunk_count=4,
                embedded_at="2026-03-14T10:00:00+00:00",
            )
        )
        db.commit()

        def _retrieve_points(
            _settings: Any,
            ids: list[int],
            *,
            with_vector: bool = True,
            with_payload: bool = False,
        ) -> dict[str, object]:
            del _settings, with_vector, with_payload
            return {
                "result": [
                    {"id": str(ids[0]), "vector": [0.1, 0.2]},
                    {"id": str(ids[1]), "vector": [0.3, 0.4]},
                ]
            }

        payload = audit_missing_vector_chunks(
            settings,
            db,
            limit=20,
            retrieve_points_fn=_retrieve_points,
        )

    assert payload["affected_docs"] == 1
    assert payload["fully_missing_docs"] == 0
    assert payload["partial_missing_docs"] == 1
    assert payload["items"][0]["doc_id"] == 68
    assert payload["items"][0]["expected_vectors"] == 4
    assert payload["items"][0]["found_vectors"] == 2
    assert payload["items"][0]["fully_missing"] is False
