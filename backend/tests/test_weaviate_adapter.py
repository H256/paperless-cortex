from __future__ import annotations

import importlib
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any

from app.config import Settings, load_settings
from app.services.search import weaviate
from app.services.search.vector_backends.weaviate_adapter import (
    WeaviateVectorStoreAdapter,
    _point_uuid,
    _score_threshold_to_distance,
)


class FakeDataOps:
    def __init__(self) -> None:
        self.inserted: list[list[object]] = []
        self.deleted_ids: list[object] = []
        self.deleted_filters: list[object] = []

    def insert_many(self, objects: list[object]) -> None:
        self.inserted.append(list(objects))

    def delete_by_id(self, point_id: object) -> None:
        self.deleted_ids.append(point_id)

    def delete_many(self, where: object) -> None:
        self.deleted_filters.append(where)


class FakeQueryOps:
    def __init__(self) -> None:
        self.near_vector_calls: list[dict[str, object]] = []
        self.fetch_calls: list[dict[str, object]] = []
        self.near_vector_response: object = SimpleNamespace(objects=[])
        self.fetch_response: object = SimpleNamespace(objects=[])

    def near_vector(self, **kwargs: object) -> object:
        self.near_vector_calls.append(dict(kwargs))
        return self.near_vector_response

    def fetch_objects(self, **kwargs: object) -> object:
        self.fetch_calls.append(dict(kwargs))
        return self.fetch_response


class FakeCollection:
    def __init__(self, name: str) -> None:
        self.name = name
        self.data = FakeDataOps()
        self.query = FakeQueryOps()


class FakeCollectionsManager:
    def __init__(self) -> None:
        self.created: list[dict[str, object]] = []
        self.existing: set[str] = set()
        self._collections: dict[str, FakeCollection] = {}

    def exists(self, name: str) -> bool:
        return name in self.existing

    def create(self, name: str, **kwargs: object) -> None:
        self.created.append({"name": name, **kwargs})
        self.existing.add(name)
        self._collections.setdefault(name, FakeCollection(name))

    def get(self, name: str) -> FakeCollection:
        self._collections.setdefault(name, FakeCollection(name))
        return self._collections[name]


class FakeClient:
    def __init__(self) -> None:
        self.collections = FakeCollectionsManager()

    def is_ready(self) -> bool:
        return True


def _settings(monkeypatch: Any) -> Settings:
    monkeypatch.setenv("VECTOR_STORE_PROVIDER", "weaviate")
    monkeypatch.delenv("VECTOR_STORE_COLLECTION", raising=False)
    monkeypatch.delenv("VECTOR_STORE_CENTROID_COLLECTION", raising=False)
    monkeypatch.setenv("WEAVIATE_HTTP_HOST", "weaviate-http")
    monkeypatch.setenv("WEAVIATE_GRPC_HOST", "weaviate-grpc")
    monkeypatch.setenv("WEAVIATE_COLLECTION", "paperless_chunks_v2")
    monkeypatch.setenv("WEAVIATE_CENTROID_COLLECTION", "paperless_chunks_v2_centroids")
    return load_settings()


@contextmanager
def _client_context(fake_client: FakeClient) -> Any:
    yield fake_client


def test_weaviate_adapter_ensure_collection_creates_chunk_and_centroid(
    monkeypatch: Any,
) -> None:
    settings = _settings(monkeypatch)
    fake_client = FakeClient()
    adapter = WeaviateVectorStoreAdapter()

    monkeypatch.setattr(weaviate, "client", lambda _settings: _client_context(fake_client))

    adapter.ensure_collection(settings, vector_size=768)

    assert fake_client.collections.created[0]["name"] == "paperless_chunks_v2"
    assert fake_client.collections.created[1]["name"] == "paperless_chunks_v2_centroids"


def test_weaviate_adapter_upsert_points_splits_chunk_and_centroid(
    monkeypatch: Any,
) -> None:
    settings = _settings(monkeypatch)
    fake_client = FakeClient()
    adapter = WeaviateVectorStoreAdapter()
    chunk_collection = fake_client.collections.get("paperless_chunks_v2")
    centroid_collection = fake_client.collections.get("paperless_chunks_v2_centroids")

    monkeypatch.setattr(weaviate, "client", lambda _settings: _client_context(fake_client))

    adapter.upsert_points(
        settings,
        [
            {
                "id": "chunk-7-0",
                "vector": [0.1, 0.2],
                "payload": {"doc_id": 7, "chunk": 0, "source": "paperless", "text": "chunk text"},
            },
            {
                "id": "doc-7",
                "vector": [0.3, 0.4],
                "payload": {"doc_id": 7, "chunk": -1, "source": "paperless", "type": "doc"},
            },
        ],
    )

    assert len(chunk_collection.data.inserted) == 1
    assert len(chunk_collection.data.inserted[0]) == 1
    assert centroid_collection.data.deleted_ids == [_point_uuid("doc-7")]
    assert len(centroid_collection.data.inserted) == 1
    assert len(centroid_collection.data.inserted[0]) == 1


def test_weaviate_adapter_search_points_routes_doc_filter_to_centroids(
    monkeypatch: Any,
) -> None:
    settings = _settings(monkeypatch)
    fake_client = FakeClient()
    adapter = WeaviateVectorStoreAdapter()
    chunk_collection = fake_client.collections.get("paperless_chunks_v2")
    centroid_collection = fake_client.collections.get("paperless_chunks_v2_centroids")
    centroid_collection.query.near_vector_response = SimpleNamespace(
        objects=[
            SimpleNamespace(
                properties={"point_id": "doc-9", "doc_id": 9, "chunk": -1, "source": "paperless", "type": "doc"},
                metadata=SimpleNamespace(distance=0.25),
            )
        ]
    )

    monkeypatch.setattr(weaviate, "client", lambda _settings: _client_context(fake_client))

    result = adapter.search_points(
        settings,
        [0.9, 0.8],
        filter_payload={"must": [{"key": "type", "match": {"value": "doc"}}]},
    )

    assert len(chunk_collection.query.near_vector_calls) == 0
    assert len(centroid_collection.query.near_vector_calls) == 1
    assert result["result"][0]["id"] == "doc-9"
    assert result["result"][0]["score"] == 0.8


def test_weaviate_adapter_search_points_converts_score_threshold_to_distance(
    monkeypatch: Any,
) -> None:
    settings = _settings(monkeypatch)
    fake_client = FakeClient()
    adapter = WeaviateVectorStoreAdapter()
    centroid_collection = fake_client.collections.get("paperless_chunks_v2_centroids")

    monkeypatch.setattr(weaviate, "client", lambda _settings: _client_context(fake_client))

    adapter.search_points(
        settings,
        [0.9, 0.8],
        filter_payload={"must": [{"key": "type", "match": {"value": "doc"}}]},
        score_threshold=0.8,
    )

    assert len(centroid_collection.query.near_vector_calls) == 1
    assert centroid_collection.query.near_vector_calls[0]["distance"] == 0.25


def test_weaviate_adapter_retrieve_points_falls_back_to_centroids(
    monkeypatch: Any,
) -> None:
    settings = _settings(monkeypatch)
    fake_client = FakeClient()
    adapter = WeaviateVectorStoreAdapter()
    chunk_collection = fake_client.collections.get("paperless_chunks_v2")
    centroid_collection = fake_client.collections.get("paperless_chunks_v2_centroids")
    chunk_collection.query.fetch_response = SimpleNamespace(
        objects=[
            SimpleNamespace(
                properties={"point_id": "1", "doc_id": 1, "chunk": 0, "source": "paperless"},
                metadata=None,
                vector=[0.1, 0.2],
            )
        ]
    )
    centroid_collection.query.fetch_response = SimpleNamespace(
        objects=[
            SimpleNamespace(
                properties={"point_id": "2", "doc_id": 2, "chunk": -1, "source": "paperless", "type": "doc"},
                metadata=None,
                vector=[0.3, 0.4],
            )
        ]
    )

    monkeypatch.setattr(weaviate, "client", lambda _settings: _client_context(fake_client))

    result = adapter.retrieve_points(settings, [1, 2], with_vector=True)

    assert len(chunk_collection.query.fetch_calls) == 1
    assert len(centroid_collection.query.fetch_calls) == 1
    assert [item["id"] for item in result["result"]] == ["1", "2"]
    assert result["result"][0]["vector"] == [0.1, 0.2]
    assert result["result"][1]["vector"] == [0.3, 0.4]


def test_weaviate_adapter_retrieve_points_reads_default_named_vector(
    monkeypatch: Any,
) -> None:
    settings = _settings(monkeypatch)
    fake_client = FakeClient()
    adapter = WeaviateVectorStoreAdapter()
    chunk_collection = fake_client.collections.get("paperless_chunks_v2")
    chunk_collection.query.fetch_response = SimpleNamespace(
        objects=[
            SimpleNamespace(
                properties={"point_id": "1", "doc_id": 1, "chunk": 0, "source": "vision"},
                metadata=None,
                vector={"default": [0.5, 0.6]},
            )
        ]
    )

    monkeypatch.setattr(weaviate, "client", lambda _settings: _client_context(fake_client))

    result = adapter.retrieve_points(settings, [1], with_vector=True)

    assert result["result"][0]["vector"] == [0.5, 0.6]


def test_weaviate_adapter_retrieve_points_uses_any_of_filter(
    monkeypatch: Any,
) -> None:
    adapter_module = importlib.import_module("app.services.search.vector_backends.weaviate_adapter")

    settings = _settings(monkeypatch)
    fake_client = FakeClient()
    adapter = WeaviateVectorStoreAdapter()

    any_of_calls: list[list[object]] = []
    original_any_of = adapter_module.Filter.any_of

    def fake_any_of(filters: list[object]) -> object:
        any_of_calls.append(filters)
        return original_any_of(filters)

    monkeypatch.setattr(adapter_module.Filter, "any_of", staticmethod(fake_any_of))
    monkeypatch.setattr(weaviate, "client", lambda _settings: _client_context(fake_client))

    adapter.retrieve_points(settings, [1, 2, 3], with_vector=False, with_payload=False)

    assert len(any_of_calls) >= 1
    assert len(any_of_calls[0]) == 3


def test_weaviate_adapter_delete_all_chunk_points_uses_chunk_collection(
    monkeypatch: Any,
) -> None:
    settings = _settings(monkeypatch)
    fake_client = FakeClient()
    fake_client.collections.existing.add("paperless_chunks_v2")
    adapter = WeaviateVectorStoreAdapter()
    chunk_collection = fake_client.collections.get("paperless_chunks_v2")
    centroid_collection = fake_client.collections.get("paperless_chunks_v2_centroids")

    monkeypatch.setattr(weaviate, "client", lambda _settings: _client_context(fake_client))

    adapter.delete_all_chunk_points(settings)

    assert len(chunk_collection.data.deleted_filters) == 1
    assert centroid_collection.data.deleted_filters == []


def test_weaviate_adapter_delete_similarity_points_targets_centroid_collection(
    monkeypatch: Any,
) -> None:
    settings = _settings(monkeypatch)
    fake_client = FakeClient()
    fake_client.collections.existing.add("paperless_chunks_v2_centroids")
    adapter = WeaviateVectorStoreAdapter()
    chunk_collection = fake_client.collections.get("paperless_chunks_v2")
    centroid_collection = fake_client.collections.get("paperless_chunks_v2_centroids")

    monkeypatch.setattr(weaviate, "client", lambda _settings: _client_context(fake_client))

    adapter.delete_similarity_points(settings, doc_id=9)

    assert chunk_collection.data.deleted_filters == []
    assert len(centroid_collection.data.deleted_filters) == 1


def test_weaviate_adapter_delete_operations_ignore_missing_collections(
    monkeypatch: Any,
) -> None:
    settings = _settings(monkeypatch)
    fake_client = FakeClient()
    adapter = WeaviateVectorStoreAdapter()

    monkeypatch.setattr(weaviate, "client", lambda _settings: _client_context(fake_client))

    adapter.delete_all_chunk_points(settings)
    adapter.delete_similarity_points(settings, doc_id=11)


def test_score_threshold_to_distance_handles_edge_values() -> None:
    assert _score_threshold_to_distance(None) is None
    assert _score_threshold_to_distance(0.0) is None
    assert _score_threshold_to_distance(0.5) == 1.0
    assert _score_threshold_to_distance(0.8) == 0.25
    assert _score_threshold_to_distance(1.0) == 0.0
