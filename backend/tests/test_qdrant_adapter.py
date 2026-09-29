from __future__ import annotations

import importlib
from contextlib import contextmanager
from typing import Any

import httpx
import pytest

from app.config import Settings, load_settings
from app.services.search.vector_backends.qdrant_adapter import QdrantVectorStoreAdapter


class _FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        self.text = "boom" if status_code >= 400 else ""

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("POST", "http://qdrant.local/points/delete")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError(
                f"status {self.status_code}", request=request, response=response
            )


class _FakeQdrantClient:
    def __init__(
        self,
        status_code: int = 200,
        put_status_codes: list[int] | None = None,
    ) -> None:
        self.status_code = status_code
        self.put_status_codes = list(put_status_codes or [])
        self.put_calls = 0
        self.post_bodies: list[dict[str, Any]] = []

    def post(self, _url: str, *, headers: Any = None, json: Any = None) -> _FakeResponse:
        self.post_bodies.append(dict(json))
        return _FakeResponse(self.status_code)

    def put(
        self, _url: str, *, headers: Any = None, json: Any = None
    ) -> _FakeResponse:
        code = (
            self.put_status_codes.pop(0)
            if self.put_status_codes
            else self.status_code
        )
        self.put_calls += 1
        return _FakeResponse(code)


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


def _two_points() -> list[dict[str, Any]]:
    return [
        {"id": 101, "vector": [0.1], "payload": {"doc_id": 1, "chunk": 0}},
        {"id": 102, "vector": [0.2], "payload": {"doc_id": 1, "chunk": 1}},
    ]


def _patch_chunker(monkeypatch: Any) -> None:
    """Force two single-point batches so the second put can fail independently."""
    adapter_module = importlib.import_module(
        "app.services.search.vector_backends.qdrant_adapter"
    )
    monkeypatch.setattr(
        adapter_module.QdrantVectorStoreAdapter,
        "_chunk_points_by_size",
        staticmethod(lambda points, max_bytes: [points[:1], points[1:]]),
    )


def test_qdrant_upsert_rolls_back_written_points_on_batch_failure(
    monkeypatch: Any,
) -> None:
    settings = _settings(monkeypatch)
    fake_client = _FakeQdrantClient(put_status_codes=[200, 500])
    _patch_client(monkeypatch, fake_client)
    _patch_chunker(monkeypatch)
    adapter = QdrantVectorStoreAdapter()

    with pytest.raises(RuntimeError, match="Qdrant upsert failed"):
        adapter.upsert_points(settings, _two_points())

    # The first (successfully persisted) batch's point IDs are deleted before the
    # error propagates; the failed batch's IDs are not.
    delete_bodies = [b for b in fake_client.post_bodies if "points" in b]
    assert delete_bodies == [{"points": [101]}]


def test_qdrant_upsert_no_rollback_when_first_batch_fails(
    monkeypatch: Any,
) -> None:
    settings = _settings(monkeypatch)
    fake_client = _FakeQdrantClient(put_status_codes=[500])
    _patch_client(monkeypatch, fake_client)
    _patch_chunker(monkeypatch)
    adapter = QdrantVectorStoreAdapter()

    with pytest.raises(RuntimeError, match="Qdrant upsert failed"):
        adapter.upsert_points(settings, _two_points())

    # Nothing was persisted before the failure, so no compensating delete is issued.
    assert fake_client.post_bodies == []


def test_qdrant_upsert_rollback_failure_does_not_mask_original(
    monkeypatch: Any,
) -> None:
    settings = _settings(monkeypatch)
    # put: batch0 ok, batch1 fails. post (compensating delete) also fails (500).
    fake_client = _FakeQdrantClient(status_code=500, put_status_codes=[200, 500])
    _patch_client(monkeypatch, fake_client)
    _patch_chunker(monkeypatch)
    adapter = QdrantVectorStoreAdapter()

    with pytest.raises(RuntimeError, match="Qdrant upsert failed"):
        adapter.upsert_points(settings, _two_points())
