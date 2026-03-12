from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

import httpx

from app.services.search import qdrant

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)


class QdrantVectorStoreAdapter:
    def provider_name(self) -> str:
        return "qdrant"

    def display_name(self) -> str:
        return "Qdrant"

    def ensure_ready(self, settings: Settings) -> None:
        if not settings.vector_store.url:
            raise RuntimeError("VECTOR_STORE_URL not set")
        if not settings.vector_store.collection:
            raise RuntimeError("VECTOR_STORE_COLLECTION not set")
        qdrant.base_url(settings)
        qdrant.collection_name(settings)

    def check_health(self, settings: Settings) -> tuple[bool, str]:
        if not settings.vector_store.url:
            return False, "VECTOR_STORE_URL not set"
        try:
            base = qdrant.base_url(settings)
            with qdrant.client(settings, timeout=5) as http:
                response = http.get(f"{base}/healthz", headers=qdrant.headers(settings))
                response.raise_for_status()
            return True, "ok"
        except (httpx.HTTPError, RuntimeError, ValueError) as exc:
            return False, exc.__class__.__name__

    def ensure_collection(
        self, settings: Settings, *, vector_size: int, distance: str = "Cosine"
    ) -> None:
        base = qdrant.base_url(settings)
        collection = qdrant.collection_name(settings)
        headers = qdrant.headers(settings)
        with qdrant.client(settings, timeout=30) as client:
            resp = client.get(f"{base}/collections/{collection}", headers=headers)
            if resp.status_code == 200:
                info = resp.json()
                config = info.get("result", {}).get("config", {}).get("params", {}).get("vectors", {})
                size = config.get("size")
                if size and int(size) != vector_size:
                    raise RuntimeError(
                        f"Qdrant collection '{collection}' has size {size}, "
                        f"but embedding size is {vector_size}. Delete or use a new collection."
                    )
                return
            if resp.status_code != 404:
                resp.raise_for_status()
            create = client.put(
                f"{base}/collections/{collection}",
                headers=headers,
                json={"vectors": {"size": vector_size, "distance": distance}},
            )
            create.raise_for_status()

    def upsert_points(self, settings: Settings, points: list[dict[str, Any]]) -> None:
        base = qdrant.base_url(settings)
        collection = qdrant.collection_name(settings)
        headers = qdrant.headers(settings)
        logger.info("Vector upsert provider=qdrant points=%s", len(points))
        with qdrant.client(settings, timeout=60) as client:
            for batch in self._chunk_points_by_size(points, max_bytes=30 * 1024 * 1024):
                response = client.put(
                    f"{base}/collections/{collection}/points",
                    headers=headers,
                    json={"points": batch},
                )
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    detail = response.text[:500]
                    raise RuntimeError(f"Qdrant upsert failed: {detail}") from exc
        logger.info("Vector upsert provider=qdrant ok")

    def delete_points_for_doc(
        self, settings: Settings, *, doc_id: int, source: str | None = None
    ) -> None:
        base = qdrant.base_url(settings)
        collection = qdrant.collection_name(settings)
        headers = qdrant.headers(settings)
        must_filters: list[dict[str, object]] = [{"key": "doc_id", "match": {"value": doc_id}}]
        if source:
            must_filters.append({"key": "source", "match": {"value": source}})
        with qdrant.client(settings, timeout=30) as client:
            response = client.post(
                f"{base}/collections/{collection}/points/delete",
                headers=headers,
                json={"filter": {"must": must_filters}},
            )
            response.raise_for_status()

    def delete_similarity_points(self, settings: Settings, *, doc_id: int | None = None) -> None:
        base = qdrant.base_url(settings)
        collection = qdrant.collection_name(settings)
        headers = qdrant.headers(settings)
        must_filters: list[dict[str, object]] = [{"key": "type", "match": {"value": "doc"}}]
        if doc_id is not None:
            must_filters.append({"key": "doc_id", "match": {"value": int(doc_id)}})
        with qdrant.client(settings, timeout=30) as client:
            response = client.post(
                f"{base}/collections/{collection}/points/delete",
                headers=headers,
                json={"filter": {"must": must_filters}},
            )
            response.raise_for_status()

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
        return qdrant.search(
            settings,
            vector,
            limit=limit,
            with_payload=with_payload,
            filter_payload=filter_payload,
            score_threshold=score_threshold,
        )

    def retrieve_points(
        self,
        settings: Settings,
        ids: list[int],
        *,
        with_vector: bool = True,
        with_payload: bool = True,
    ) -> dict[str, Any]:
        return qdrant.retrieve_points(
            settings,
            ids,
            with_vector=with_vector,
            with_payload=with_payload,
        )

    @staticmethod
    def _chunk_points_by_size(
        points: list[dict[str, Any]], max_bytes: int
    ) -> list[list[dict[str, Any]]]:
        if not points:
            return []
        batches: list[list[dict[str, Any]]] = []
        current: list[dict[str, Any]] = []
        current_size = 0
        for point in points:
            point_json = json.dumps(point, ensure_ascii=False)
            point_size = len(point_json.encode("utf-8"))
            if current and current_size + point_size > max_bytes:
                batches.append(current)
                current = []
                current_size = 0
            current.append(point)
            current_size += point_size
        if current:
            batches.append(current)
        return batches


qdrant_adapter = QdrantVectorStoreAdapter()
