from __future__ import annotations

import uuid as uuid_package
from typing import TYPE_CHECKING, Any, cast

from weaviate.classes.config import Configure, DataType, Property
from weaviate.classes.data import DataObject
from weaviate.classes.query import Filter, MetadataQuery

from app.services.search import weaviate

if TYPE_CHECKING:
    from weaviate.collections.collection.sync import Collection

    from app.config import Settings

_POINT_NAMESPACE = uuid_package.UUID("7a0c47a8-c4f2-4a24-a334-890bb89cf2c5")


def _point_uuid(point_id: object) -> uuid_package.UUID:
    return uuid_package.uuid5(_POINT_NAMESPACE, str(point_id))


def _chunk_properties() -> list[Property]:
    return [
        Property(name="point_id", data_type=DataType.TEXT),
        Property(name="doc_id", data_type=DataType.INT),
        Property(name="chunk", data_type=DataType.INT),
        Property(name="text", data_type=DataType.TEXT),
        Property(name="page", data_type=DataType.INT),
        Property(name="source", data_type=DataType.TEXT),
        Property(name="quality_score", data_type=DataType.INT),
        Property(name="bbox", data_type=DataType.NUMBER_ARRAY),
        Property(name="type", data_type=DataType.TEXT),
    ]


def _centroid_properties() -> list[Property]:
    return [
        Property(name="point_id", data_type=DataType.TEXT),
        Property(name="doc_id", data_type=DataType.INT),
        Property(name="chunk", data_type=DataType.INT),
        Property(name="source", data_type=DataType.TEXT),
        Property(name="type", data_type=DataType.TEXT),
    ]


def _collection(client: Any, name: str) -> Collection[Any, Any]:
    return cast("Collection[Any, Any]", client.collections.get(name))


def _chunk_collection(client: Any, settings: Settings) -> Collection[Any, Any]:
    return _collection(client, weaviate.chunk_collection_name(settings))


def _centroid_collection(client: Any, settings: Settings) -> Collection[Any, Any]:
    return _collection(client, weaviate.centroid_collection_name(settings))


def _properties_from_point(point: dict[str, Any]) -> dict[str, Any]:
    payload = point.get("payload")
    payload_dict = payload if isinstance(payload, dict) else {}
    bbox = payload_dict.get("bbox")
    bbox_values = [float(value) for value in bbox] if isinstance(bbox, list) else None
    properties: dict[str, Any] = {
        "point_id": str(point["id"]),
        "doc_id": payload_dict.get("doc_id"),
        "chunk": payload_dict.get("chunk"),
        "source": payload_dict.get("source"),
        "type": payload_dict.get("type"),
    }
    if "text" in payload_dict:
        properties["text"] = payload_dict.get("text")
    if payload_dict.get("page") is not None:
        properties["page"] = payload_dict.get("page")
    if payload_dict.get("quality_score") is not None:
        properties["quality_score"] = payload_dict.get("quality_score")
    if bbox_values is not None:
        properties["bbox"] = bbox_values
    return properties


def _to_data_object(point: dict[str, Any]) -> DataObject[dict[str, Any], None]:
    return DataObject(
        uuid=_point_uuid(point["id"]),
        properties=_properties_from_point(point),
        vector=point.get("vector"),
    )


def _combine_or(filters: list[Any]) -> Any | None:
    if not filters:
        return None
    current = filters[0]
    for item in filters[1:]:
        current = current | item
    return current


def _combine_and(filters: list[Any]) -> Any | None:
    if not filters:
        return None
    current = filters[0]
    for item in filters[1:]:
        current = current & item
    return current


def _translate_filter(filter_payload: dict[str, Any] | None, *, centroid: bool) -> Any | None:
    if not isinstance(filter_payload, dict):
        return None
    must_filters: list[Any] = []
    must_not_filters: list[Any] = []
    for item in filter_payload.get("must", []):
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        value = (item.get("match") or {}).get("value")
        if key == "type":
            if centroid and value == "doc":
                continue
            if not centroid and value == "doc":
                continue
        if key is None:
            continue
        must_filters.append(Filter.by_property(str(key)).equal(value))
    for item in filter_payload.get("must_not", []):
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        value = (item.get("match") or {}).get("value")
        if key == "type" and value == "doc" and not centroid:
            continue
        if key is None:
            continue
        must_not_filters.append(Filter.by_property(str(key)).not_equal(value))
    filters = [*_combine_list(must_filters), *_combine_list(must_not_filters)]
    return _combine_and(filters)


def _combine_list(filters: list[Any]) -> list[Any]:
    combined = _combine_and(filters)
    return [combined] if combined is not None else []


def _result_object(raw: Any, *, include_vector: bool = False) -> dict[str, Any]:
    properties = getattr(raw, "properties", None) or {}
    metadata = getattr(raw, "metadata", None)
    distance = getattr(metadata, "distance", None)
    vector = getattr(raw, "vector", None) if include_vector else None
    payload = {
        key: properties.get(key)
        for key in ("doc_id", "chunk", "text", "page", "source", "quality_score", "bbox", "type")
        if key in properties
    }
    score = 1.0 / (1.0 + float(distance)) if isinstance(distance, (int, float)) else None
    result: dict[str, Any] = {
        "id": properties.get("point_id") or str(getattr(raw, "uuid", "")),
        "payload": payload,
    }
    if score is not None:
        result["score"] = score
    if include_vector and isinstance(vector, list):
        result["vector"] = vector
    return result


class WeaviateVectorStoreAdapter:
    def provider_name(self) -> str:
        return "weaviate"

    def display_name(self) -> str:
        return "Weaviate"

    def ensure_ready(self, settings: Settings) -> None:
        weaviate.http_host(settings)
        weaviate.grpc_host(settings)
        weaviate.chunk_collection_name(settings)
        weaviate.centroid_collection_name(settings)

    def check_health(self, settings: Settings) -> tuple[bool, str]:
        try:
            self.ensure_ready(settings)
            with weaviate.client(settings) as client:
                return (True, "ok") if client.is_ready() else (False, "not ready")
        except RuntimeError as exc:
            return False, str(exc)
        except Exception as exc:
            return False, exc.__class__.__name__

    def ensure_collection(
        self, settings: Settings, *, vector_size: int, distance: str = "Cosine"
    ) -> None:
        del vector_size, distance
        self.ensure_ready(settings)
        with weaviate.client(settings) as client:
            chunk_name = weaviate.chunk_collection_name(settings)
            centroid_name = weaviate.centroid_collection_name(settings)
            if not client.collections.exists(chunk_name):
                client.collections.create(
                    chunk_name,
                    properties=_chunk_properties(),
                    vector_config=Configure.Vectors.self_provided(),
                )
            if not client.collections.exists(centroid_name):
                client.collections.create(
                    centroid_name,
                    properties=_centroid_properties(),
                    vector_config=Configure.Vectors.self_provided(),
                )

    def upsert_points(self, settings: Settings, points: list[dict[str, Any]]) -> None:
        self.ensure_ready(settings)
        centroid_points = [
            point
            for point in points
            if isinstance(point.get("payload"), dict)
            and (point["payload"].get("type") == "doc" or point["payload"].get("chunk") == -1)
        ]
        chunk_points = [point for point in points if point not in centroid_points]
        with weaviate.client(settings) as client:
            if chunk_points:
                _chunk_collection(client, settings).data.insert_many(
                    [_to_data_object(point) for point in chunk_points]
                )
            if centroid_points:
                centroid_collection = _centroid_collection(client, settings)
                for point in centroid_points:
                    centroid_collection.data.delete_by_id(_point_uuid(point["id"]))
                centroid_collection.data.insert_many(
                    [_to_data_object(point) for point in centroid_points]
                )

    def delete_points_for_doc(
        self, settings: Settings, *, doc_id: int, source: str | None = None
    ) -> None:
        self.ensure_ready(settings)
        filters: list[Any] = [Filter.by_property("doc_id").equal(doc_id)]
        if source:
            filters.append(Filter.by_property("source").equal(source))
        where = _combine_and(filters)
        if where is None:
            return
        with weaviate.client(settings) as client:
            _chunk_collection(client, settings).data.delete_many(where)

    def delete_similarity_points(self, settings: Settings, *, doc_id: int | None = None) -> None:
        self.ensure_ready(settings)
        filters: list[Any] = []
        if doc_id is not None:
            filters.append(Filter.by_property("doc_id").equal(int(doc_id)))
        where = _combine_and(filters)
        with weaviate.client(settings) as client:
            collection = _centroid_collection(client, settings)
            if where is None:
                collection.data.delete_many(Filter.by_property("type").equal("doc"))
                return
            collection.data.delete_many(where)

    def search_points(
        self,
        settings: Settings,
        vector: list[float],
        *,
        limit: int = 5,
        with_payload: bool = True,
        filter_payload: dict[str, Any] | None = None,
        score_threshold: float | None = None,
    ) -> dict[str, Any]:
        self.ensure_ready(settings)
        centroid = self._use_centroid_collection(filter_payload)
        where = _translate_filter(filter_payload, centroid=centroid)
        with weaviate.client(settings) as client:
            collection = _centroid_collection(client, settings) if centroid else _chunk_collection(client, settings)
            response = collection.query.near_vector(
                near_vector=vector,
                limit=max(1, limit),
                distance=score_threshold if score_threshold is not None else None,
                filters=where,
                include_vector=not with_payload,
                return_metadata=MetadataQuery(distance=True),
                return_properties=True,
            )
        objects = getattr(response, "objects", [])
        return {"result": [_result_object(obj, include_vector=not with_payload) for obj in objects]}

    def retrieve_points(
        self,
        settings: Settings,
        ids: list[int],
        *,
        with_vector: bool = True,
        with_payload: bool = True,
    ) -> dict[str, Any]:
        self.ensure_ready(settings)
        point_ids = [str(point_id) for point_id in ids]
        with weaviate.client(settings) as client:
            results = self._fetch_collection_points(
                _chunk_collection(client, settings),
                point_ids,
                with_vector=with_vector,
                with_payload=with_payload,
            )
            missing = [point_id for point_id in point_ids if point_id not in {str(item["id"]) for item in results}]
            if missing:
                results.extend(
                    self._fetch_collection_points(
                        _centroid_collection(client, settings),
                        missing,
                        with_vector=with_vector,
                        with_payload=with_payload,
                    )
                )
        return {"result": results}

    @staticmethod
    def _fetch_collection_points(
        collection: Collection[Any, Any],
        point_ids: list[str],
        *,
        with_vector: bool,
        with_payload: bool,
    ) -> list[dict[str, Any]]:
        if not point_ids:
            return []
        filter_parts = [Filter.by_property("point_id").equal(point_id) for point_id in point_ids]
        where = _combine_or(filter_parts)
        if where is None:
            return []
        response = collection.query.fetch_objects(
            filters=where,
            limit=len(point_ids),
            include_vector=with_vector,
            return_properties=with_payload,
        )
        objects = getattr(response, "objects", [])
        return [_result_object(obj, include_vector=with_vector) for obj in objects]

    @staticmethod
    def _use_centroid_collection(filter_payload: dict[str, Any] | None) -> bool:
        if not isinstance(filter_payload, dict):
            return False
        for item in filter_payload.get("must", []):
            if not isinstance(item, dict):
                continue
            if item.get("key") == "type" and (item.get("match") or {}).get("value") == "doc":
                return True
        return False


weaviate_adapter = WeaviateVectorStoreAdapter()
