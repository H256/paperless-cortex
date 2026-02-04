from __future__ import annotations

import httpx

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
) -> dict:
    base = base_url(settings)
    collection = collection_name(settings)
    with client(settings, timeout=30) as http:
        response = http.post(
            f"{base}/collections/{collection}/points/search",
            headers=headers(settings),
            json={"vector": vector, "limit": limit, "with_payload": with_payload},
        )
        response.raise_for_status()
        return response.json()
