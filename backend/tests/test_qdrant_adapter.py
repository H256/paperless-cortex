from __future__ import annotations

import importlib
from contextlib import contextmanager
from typing import Any

import httpx

from app.config import Settings, load_settings
from app.services.search.vector_backends.qdrant_adapter import QdrantVectorStoreAdapter


class _FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("POST", "http://qdrant.local/points/delete")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError(
                f"status {self.status_code}", request=request, response=response
            )


class _FakeQdrantClient:
    def __init__(self, status_code: int = 200) -> None:
        self.status_code = status_code
        self.post_bodies: list[dict[str, Any]] = []

    def post(self, _url: str, *, headers: Any = None, json: Any = None) -> _FakeResponse:
        self.post_bodies.append(dict(json))
        return _FakeResponse(self.status_code)


@contextmanager
def _client_context(fake_client: _FakeQdrantClient) -> Any:
    yield fake_client


def _settings(monkeypatch: Any) -> Settings:
    monkeypatch.setenv("VECTOR_STORE_PROVIDER", "qdrant")
    monkeypatch.delenv("VECTOR_STORE_URL", raising=False)
    monkeypatch.delenv("VECTOR_STORE_COLLECTION", raising=False)
    monkeypatch.setenv("QDRANT_URL", "http://qdrant.local")
    monkeypatch.setenv("QDRANT_COLLECTION", "paperless_chunks")
    return load_settings()


def _patch_client(monkeypatch: Any, fake_client: _FakeQdrantClient) -> None:
    adapter_module = importlib.import_module(
        "app.services.search.vector_backends.qdrant_adapter"
    )
    monkeypatch.setattr(
        adapter_module.qdrant, "client", lambda _settings, timeout: _client_context(fake_client)
    )


def test_qdrant_adapter_delete_points_for_doc_single_source_builds_value_filter(
    monkeypatch: Any,
) -> None:
    settings = _settings(monkeypatch)
    fake_client = _FakeQdrantClient()
    _patch_client(monkeypatch, fake_client)
    adapter = QdrantVectorStoreAdapter()

    adapter.delete_points_for_doc(settings, doc_id=7, source="vision_ocr")

    assert len(fake_client.post_bodies) == 1
    must = fake_client.post_bodies[0]["filter"]["must"]
    assert {"key": "doc_id", "match": {"value": 7}} in must
    assert {"key": "source", "match": {"value": "vision_ocr"}} in must
    assert len(must) == 2


def test_qdrant_adapter_delete_points_for_doc_multi_source_builds_any_filter(
    monkeypatch: Any,
) -> None:
    settings = _settings(monkeypatch)
    fake_client = _FakeQdrantClient()
    _patch_client(monkeypatch, fake_client)
    adapter = QdrantVectorStoreAdapter()

    adapter.delete_points_for_doc(settings, doc_id=7, source=("paperless_ocr", "pdf_text"))

    must = fake_client.post_bodies[0]["filter"]["must"]
    assert {"key": "doc_id", "match": {"value": 7}} in must
    assert {"key": "source", "match": {"any": ["paperless_ocr", "pdf_text"]}} in must
    assert len(must) == 2


def test_qdrant_adapter_delete_points_for_doc_without_source_omits_source_filter(
    monkeypatch: Any,
) -> None:
    settings = _settings(monkeypatch)
    fake_client = _FakeQdrantClient()
    _patch_client(monkeypatch, fake_client)
    adapter = QdrantVectorStoreAdapter()

    adapter.delete_points_for_doc(settings, doc_id=7)

    must = fake_client.post_bodies[0]["filter"]["must"]
    assert must == [{"key": "doc_id", "match": {"value": 7}}]


def test_qdrant_adapter_delete_points_for_doc_ignores_missing_collection(
    monkeypatch: Any,
) -> None:
    settings = _settings(monkeypatch)
    fake_client = _FakeQdrantClient(status_code=404)
    _patch_client(monkeypatch, fake_client)
    adapter = QdrantVectorStoreAdapter()

    adapter.delete_points_for_doc(settings, doc_id=7, source="vision_ocr")

    assert len(fake_client.post_bodies) == 1


def test_qdrant_adapter_delete_all_chunk_points_filters_non_doc_type(
    monkeypatch: Any,
) -> None:
    settings = _settings(monkeypatch)
    fake_client = _FakeQdrantClient()
    _patch_client(monkeypatch, fake_client)
    adapter = QdrantVectorStoreAdapter()

    adapter.delete_all_chunk_points(settings)

    assert len(fake_client.post_bodies) == 1
    assert fake_client.post_bodies[0]["filter"] == {
        "must_not": [{"key": "type", "match": {"value": "doc"}}]
    }


def test_qdrant_adapter_delete_all_chunk_points_ignores_missing_collection(
    monkeypatch: Any,
) -> None:
    settings = _settings(monkeypatch)
    fake_client = _FakeQdrantClient(status_code=404)
    _patch_client(monkeypatch, fake_client)
    adapter = QdrantVectorStoreAdapter()

    adapter.delete_all_chunk_points(settings)

    assert len(fake_client.post_bodies) == 1
