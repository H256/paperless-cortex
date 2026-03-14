from __future__ import annotations

import atexit
import threading
from contextlib import contextmanager
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from collections.abc import Iterator

    from app.config import Settings

_CLIENT_LOCK = threading.Lock()
_CLIENTS: dict[tuple[float | None, bool], httpx.Client] = {}


def base_url(settings: Settings) -> str:
    if not settings.vector_store_url:
        raise RuntimeError("VECTOR_STORE_URL not set")
    return settings.vector_store_url.rstrip("/")


def collection_name(settings: Settings) -> str:
    if not settings.vector_store_collection:
        raise RuntimeError("VECTOR_STORE_COLLECTION not set")
    return settings.vector_store_collection


def headers(settings: Settings) -> dict[str, str]:
    if settings.vector_store_api_key:
        return {"api-key": settings.vector_store_api_key}
    return {}


def clear_client_pool() -> None:
    with _CLIENT_LOCK:
        clients = list(_CLIENTS.values())
        _CLIENTS.clear()
    for pooled_client in clients:
        pooled_client.close()


@atexit.register
def _close_pooled_clients() -> None:
    clear_client_pool()


def _client_key(settings: Settings, timeout: float | None) -> tuple[float | None, bool]:
    return (float(timeout) if timeout is not None else None, bool(settings.httpx_verify_tls))


def _shared_client(settings: Settings, timeout: float) -> httpx.Client:
    key = _client_key(settings, timeout)
    with _CLIENT_LOCK:
        pooled_client = _CLIENTS.get(key)
        if pooled_client is None or pooled_client.is_closed:
            pooled_client = httpx.Client(timeout=timeout, verify=settings.httpx_verify_tls)
            _CLIENTS[key] = pooled_client
        return pooled_client


@contextmanager
def client(settings: Settings, timeout: float) -> Iterator[httpx.Client]:
    yield _shared_client(settings, timeout)


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
