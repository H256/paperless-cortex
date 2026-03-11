from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from app.config import Settings


def base_url(settings: Settings) -> str:
    if not settings.qdrant_url:
        raise RuntimeError("QDRANT_URL not set")
    return settings.qdrant_url.rstrip("/")


def collection_name(settings: Settings) -> str:
    if not settings.qdrant_collection:
        raise RuntimeError("QDRANT_COLLECTION not set")
    return settings.qdrant_collection


def headers(settings: Settings) -> dict[str, str]:
    if settings.qdrant_api_key:
        return {"api-key": settings.qdrant_api_key}
    return {}


def client(settings: Settings, timeout: float) -> httpx.Client:
    return httpx.Client(timeout=timeout, verify=settings.httpx_verify_tls)


def search(
    settings: Settings,
    vector: list[float],
    *,
    limit: int = 5,
    with_payload: bool = True,
    filter_payload: dict | None = None,
    score_threshold: float | None = None,
) -> dict:
    base = base_url(settings)
    collection = collection_name(settings)
    payload: dict[str, object] = {"vector": vector, "limit": limit, "with_payload": with_payload}
    if filter_payload:
        payload["filter"] = filter_payload
    if score_threshold is not None:
        payload["score_threshold"] = score_threshold
    with client(settings, timeout=30) as http:
        response = http.post(
            f"{base}/collections/{collection}/points/search",
            headers=headers(settings),
            json=payload,
        )
        response.raise_for_status()
        return response.json()


def retrieve_points(
    settings: Settings,
    ids: list[int],
    *,
    with_vector: bool = True,
    with_payload: bool = True,
) -> dict:
    base = base_url(settings)
    collection = collection_name(settings)
    payload: dict[str, object] = {
        "ids": ids,
        "with_vector": with_vector,
        "with_payload": with_payload,
    }
    with client(settings, timeout=30) as http:
        # Qdrant API versions differ here: some expose /points/retrieve,
        # others use /points for batch retrieval by ids.
        response = http.post(
            f"{base}/collections/{collection}/points/retrieve",
            headers=headers(settings),
            json=payload,
        )
        if response.status_code == 404:
            response = http.post(
                f"{base}/collections/{collection}/points",
                headers=headers(settings),
                json=payload,
            )
        response.raise_for_status()
        return response.json()
