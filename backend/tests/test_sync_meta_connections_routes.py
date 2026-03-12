from __future__ import annotations

from typing import Any

from app.config import load_settings
from app.models import Document, DocumentEmbedding


def test_sync_tags_route(api_client: Any, monkeypatch: Any) -> None:
    import app.routes.sync as sync_routes

    monkeypatch.setattr(sync_routes, "sync_tags_page", lambda *args, **kwargs: (7, 3))

    response = api_client.post("/sync/tags", params={"page": 2, "page_size": 50})
    assert response.status_code == 200
    assert response.json() == {"count": 7, "upserted": 3}


def test_sync_correspondents_route(api_client: Any, monkeypatch: Any) -> None:
    import app.routes.sync as sync_routes

    monkeypatch.setattr(sync_routes, "sync_correspondents_page", lambda *args, **kwargs: (5, 2))

    response = api_client.post("/sync/correspondents", params={"page": 1, "page_size": 20})
    assert response.status_code == 200
    assert response.json() == {"count": 5, "upserted": 2}


def test_sync_document_types_route(api_client: Any, monkeypatch: Any) -> None:
    import app.routes.sync as sync_routes

    monkeypatch.setattr(sync_routes, "sync_document_types_page", lambda *args, **kwargs: (4, 4))

    response = api_client.post("/sync/document-types")
    assert response.status_code == 200
    assert response.json() == {"count": 4, "upserted": 4}


def test_sync_embed_documents_uses_embed_text(session_factory: Any, monkeypatch: Any) -> None:
    import app.routes.sync as sync_routes
    import app.services.documents.sync_operations as sync_operations

    monkeypatch.setenv("EMBEDDING_MODEL", "test-embed-model")

    settings = load_settings()
    session_local = session_factory
    with session_local() as db:
        doc = Document(id=901, title="Doc", content="hello world")
        db.add(doc)
        db.commit()
        db.refresh(doc)

        monkeypatch.setattr(sync_operations, "ensure_embedding_collection", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(sync_operations, "collect_page_texts", lambda *_args, **_kwargs: ([], [], []))
        monkeypatch.setattr(
            sync_operations,
            "chunk_document_with_pages",
            lambda *_args, **_kwargs: [{"text": "hello chunk", "page": None, "source": "paperless_ocr"}],
        )
        monkeypatch.setattr(sync_operations, "delete_points_for_doc", lambda *_args, **_kwargs: None)

        embed_inputs: list[str] = []
        def _embed_text(_settings: Any, text: str) -> list[float]:
            embed_inputs.append(text)
            return [0.1, 0.2, 0.3]

        monkeypatch.setattr(sync_operations, "embed_text", _embed_text)
        monkeypatch.setattr(sync_operations, "upsert_points", lambda *_args, **_kwargs: None)

        embedded = sync_routes._embed_documents(db, settings, [doc], force_embed=False)

        assert embedded == 1
        assert embed_inputs == ["hello chunk"]
        row = db.get(DocumentEmbedding, 901)
        assert row is not None
        assert row.chunk_count == 1


def test_meta_routes(api_client: Any, monkeypatch: Any) -> None:
    import app.routes.meta as meta_routes

    monkeypatch.setattr(
        meta_routes.paperless,
        "list_tags",
        lambda *_args, **_kwargs: {"count": 1, "next": None, "previous": None, "results": [{"id": 10, "name": "tax"}]},
    )
    monkeypatch.setattr(
        meta_routes.paperless,
        "list_correspondents",
        lambda *_args, **_kwargs: {"count": 1, "next": None, "previous": None, "results": [{"id": 20, "name": "ACME"}]},
    )
    monkeypatch.setattr(meta_routes.paperless, "get_document_type", lambda *_args, **_kwargs: {"id": 30, "name": "invoice"})
    monkeypatch.setattr(meta_routes.paperless, "get_correspondent", lambda *_args, **_kwargs: {"id": 20, "name": "ACME"})

    tags_response = api_client.get("/tags")
    assert tags_response.status_code == 200
    assert tags_response.json()["results"][0]["name"] == "tax"

    correspondents_response = api_client.get("/correspondents")
    assert correspondents_response.status_code == 200
    assert correspondents_response.json()["results"][0]["name"] == "ACME"

    doc_type_response = api_client.get("/document-types/30")
    assert doc_type_response.status_code == 200
    assert doc_type_response.json()["name"] == "invoice"

    correspondent_response = api_client.get("/correspondents/20")
    assert correspondent_response.status_code == 200
    assert correspondent_response.json()["name"] == "ACME"


def test_connections_route(api_client: Any, monkeypatch: Any) -> None:
    import app.routes.connections as connections_routes

    monkeypatch.setattr(
        connections_routes,
        "run_all",
        lambda *_args, **_kwargs: [
            {"service": "paperless", "status": "ok", "detail": "reachable", "latency_ms": 12},
            {"service": "qdrant", "status": "ok", "detail": "reachable", "latency_ms": 8},
        ],
    )

    response = api_client.get("/connections/")
    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["service"] == "paperless"
    assert payload[1]["service"] == "qdrant"
