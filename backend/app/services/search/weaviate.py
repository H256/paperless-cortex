from __future__ import annotations

import atexit
import threading
from contextlib import contextmanager
from typing import TYPE_CHECKING

import weaviate
from weaviate.classes.init import Auth

if TYPE_CHECKING:
    from collections.abc import Iterator

    from weaviate import WeaviateClient

    from app.config import Settings

_CLIENT_LOCK = threading.Lock()
_CLIENTS: dict[tuple[str, int, bool, str, int, bool, bool], WeaviateClient] = {}


def http_host(settings: Settings) -> str:
    if not settings.weaviate_http_host:
        raise RuntimeError("WEAVIATE_HTTP_HOST not set")
    return settings.weaviate_http_host


def http_port(settings: Settings) -> int:
    return int(settings.weaviate_http_port)


def grpc_host(settings: Settings) -> str:
    if not settings.weaviate_grpc_host:
        raise RuntimeError("WEAVIATE_GRPC_HOST not set")
    return settings.weaviate_grpc_host


def grpc_port(settings: Settings) -> int:
    return int(settings.weaviate_grpc_port)


def chunk_collection_name(settings: Settings) -> str:
    if not settings.vector_store_collection:
        raise RuntimeError("VECTOR_STORE_COLLECTION not set")
    return settings.vector_store_collection


def centroid_collection_name(settings: Settings) -> str:
    if not settings.vector_store_centroid_collection:
        raise RuntimeError("VECTOR_STORE_CENTROID_COLLECTION not set")
    return settings.vector_store_centroid_collection


def clear_client_pool() -> None:
    with _CLIENT_LOCK:
        clients = list(_CLIENTS.values())
        _CLIENTS.clear()
    for client in clients:
        client.close()


@atexit.register
def _close_pooled_clients() -> None:
    clear_client_pool()


def _client_key(settings: Settings) -> tuple[str, int, bool, str, int, bool, bool]:
    return (
        http_host(settings),
        http_port(settings),
        bool(settings.weaviate_http_secure),
        grpc_host(settings),
        grpc_port(settings),
        bool(settings.weaviate_grpc_secure),
        bool(settings.weaviate_api_key),
    )


def _shared_client(settings: Settings) -> WeaviateClient:
    key = _client_key(settings)
    with _CLIENT_LOCK:
        client = _CLIENTS.get(key)
        if client is None:
            auth = Auth.api_key(settings.weaviate_api_key) if settings.weaviate_api_key else None
            client = weaviate.connect_to_custom(
                http_host=http_host(settings),
                http_port=http_port(settings),
                http_secure=settings.weaviate_http_secure,
                grpc_host=grpc_host(settings),
                grpc_port=grpc_port(settings),
                grpc_secure=settings.weaviate_grpc_secure,
                auth_credentials=auth,
            )
            _CLIENTS[key] = client
        return client


@contextmanager
def client(settings: Settings) -> Iterator[WeaviateClient]:
    yield _shared_client(settings)
