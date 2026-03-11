from __future__ import annotations

import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from app.config import Settings

_CACHE_LOCK = threading.Lock()
_DOC_CACHE: dict[int, tuple[float, dict[str, Any]]] = {}
_LIST_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_DOC_CACHE_TTL_SECONDS = 10
_LIST_CACHE_TTL_SECONDS = 10


def _cache_enabled(settings: Settings, ttl_seconds: int) -> bool:
    if int(ttl_seconds) <= 0:
        return False
    if not settings.paperless_base_url:
        return False
    return not os.getenv("PYTEST_CURRENT_TEST")


def base_url(settings: Settings) -> str | None:
    """Extract the base URL for Paperless-NGX from settings.

    Normalizes the base URL by removing trailing slashes and /api suffix.

    Args:
        settings: Application settings containing Paperless configuration

    Returns:
        Normalized base URL, or None if not configured.

    Example:
        >>> settings = Settings(paperless_base_url="http://localhost:8000/api/")
        >>> base_url(settings)
        'http://localhost:8000'
    """
    if not settings.paperless_base_url:
        return None
    base = settings.paperless_base_url.rstrip("/")
    if base.endswith("/api"):
        base = base[:-4]
    return base


def _api_base(settings: Settings) -> str:
    base = base_url(settings)
    if not base:
        return "/api"
    return f"{base}/api"


def client(settings: Settings) -> httpx.Client:
    """Create an authenticated HTTPX client for Paperless-NGX API.

    The client is configured with the API token, base URL, and timeout.

    Args:
        settings: Application settings with Paperless credentials

    Returns:
        Configured HTTPX client ready for API calls

    Raises:
        RuntimeError: If PAPERLESS_BASE_URL or PAPERLESS_API_TOKEN not set

    Example:
        >>> with client(settings) as c:
        ...     response = c.get("/documents/")
    """
    if not settings.paperless_base_url or not settings.paperless_api_token:
        raise RuntimeError("PAPERLESS_BASE_URL/PAPERLESS_API_TOKEN not set")
    return httpx.Client(
        base_url=_api_base(settings),
        headers={"Authorization": f"Token {settings.paperless_api_token}"},
        timeout=15,
        verify=settings.httpx_verify_tls,
    )


def list_documents(
    settings: Settings,
    page: int = 1,
    page_size: int = 20,
    ordering: str | None = None,
    correspondent__id: int | None = None,
    tags__id: int | None = None,
    document_date__gte: str | None = None,
    document_date__lte: str | None = None,
    modified__gte: str | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {"page": page, "page_size": page_size}
    if ordering:
        params["ordering"] = ordering
    if correspondent__id is not None:
        params["correspondent__id"] = correspondent__id
    if tags__id is not None:
        params["tags__id"] = tags__id
    if document_date__gte:
        params["document_date__gte"] = document_date__gte
    if document_date__lte:
        params["document_date__lte"] = document_date__lte
    if modified__gte:
        params["modified__gte"] = modified__gte
    with client(settings) as http:
        response = http.get("/documents/", params=params)
        response.raise_for_status()
        return response.json()


def get_document(settings: Settings, doc_id: int) -> dict[str, Any]:
    with client(settings) as http:
        response = http.get(f"/documents/{doc_id}/")
        response.raise_for_status()
        return response.json()


def get_document_cached(
    settings: Settings, doc_id: int, *, ttl_seconds: int = _DOC_CACHE_TTL_SECONDS
) -> dict[str, Any]:
    if not _cache_enabled(settings, ttl_seconds):
        return get_document(settings, doc_id)
    now = time.time()
    with _CACHE_LOCK:
        cached = _DOC_CACHE.get(int(doc_id))
        if cached and (now - cached[0]) < max(0, int(ttl_seconds)):
            return dict(cached[1])
    payload = get_document(settings, doc_id)
    with _CACHE_LOCK:
        _DOC_CACHE[int(doc_id)] = (now, payload)
    return dict(payload)


def invalidate_document_cache(doc_id: int, *, clear_list_cache: bool = True) -> None:
    normalized = int(doc_id)
    with _CACHE_LOCK:
        _DOC_CACHE.pop(normalized, None)
        if clear_list_cache:
            _LIST_CACHE.clear()


def get_documents_cached(
    settings: Settings,
    doc_ids: list[int],
    *,
    ttl_seconds: int = _DOC_CACHE_TTL_SECONDS,
    max_workers: int = 8,
) -> dict[int, dict[str, Any]]:
    unique_ids: list[int] = []
    seen: set[int] = set()
    for raw_id in doc_ids:
        doc_id = int(raw_id)
        if doc_id <= 0 or doc_id in seen:
            continue
        seen.add(doc_id)
        unique_ids.append(doc_id)
    if not unique_ids:
        return {}

    if not _cache_enabled(settings, ttl_seconds):
        return {doc_id: get_document(settings, doc_id) for doc_id in unique_ids}

    now = time.time()
    ttl = max(0, int(ttl_seconds))
    cached_results: dict[int, dict[str, Any]] = {}
    missing_ids: list[int] = []
    with _CACHE_LOCK:
        for doc_id in unique_ids:
            cached = _DOC_CACHE.get(doc_id)
            if cached and (now - cached[0]) < ttl:
                cached_results[doc_id] = dict(cached[1])
            else:
                missing_ids.append(doc_id)

    if not missing_ids:
        return cached_results

    worker_count = max(1, min(int(max_workers), len(missing_ids)))
    fetched_results: dict[int, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_by_doc = {
            executor.submit(get_document, settings, doc_id): doc_id for doc_id in missing_ids
        }
        for future in as_completed(future_by_doc):
            doc_id = future_by_doc[future]
            payload = future.result()
            fetched_results[doc_id] = payload

    with _CACHE_LOCK:
        stamp = time.time()
        for doc_id, payload in fetched_results.items():
            _DOC_CACHE[doc_id] = (stamp, payload)

    return {
        **cached_results,
        **{doc_id: dict(payload) for doc_id, payload in fetched_results.items()},
    }


def list_documents_cached(
    settings: Settings,
    *,
    ttl_seconds: int = _LIST_CACHE_TTL_SECONDS,
    **kwargs: Any,
) -> dict[str, Any]:
    if not _cache_enabled(settings, ttl_seconds):
        return list_documents(settings, **kwargs)
    normalized = {key: value for key, value in kwargs.items() if value is not None}
    cache_key = json.dumps(normalized, sort_keys=True, ensure_ascii=False)
    now = time.time()
    with _CACHE_LOCK:
        cached = _LIST_CACHE.get(cache_key)
        if cached and (now - cached[0]) < max(0, int(ttl_seconds)):
            return dict(cached[1])
    payload = list_documents(settings, **kwargs)
    with _CACHE_LOCK:
        _LIST_CACHE[cache_key] = (now, payload)
    return dict(payload)


def get_document_pdf(settings: Settings, doc_id: int) -> bytes:
    with client(settings) as http:
        response = http.get(f"/documents/{doc_id}/download/")
        response.raise_for_status()
        return response.content


def list_tags(settings: Settings, page: int = 1, page_size: int = 50) -> dict[str, Any]:
    with client(settings) as http:
        response = http.get("/tags/", params={"page": page, "page_size": page_size})
        response.raise_for_status()
        return response.json()


def list_all_tags(settings: Settings, page_size: int = 200) -> list[dict[str, Any]]:
    page = 1
    items: list[dict[str, Any]] = []
    while True:
        payload = list_tags(settings, page=page, page_size=page_size)
        rows = payload.get("results") or []
        items.extend([row for row in rows if isinstance(row, dict)])
        if not payload.get("next"):
            break
        page += 1
    return items


def create_tag(settings: Settings, name: str) -> dict[str, Any]:
    payload = {"name": str(name or "").strip()}
    with client(settings) as http:
        response = http.post("/tags/", json=payload)
        response.raise_for_status()
        return response.json()


def list_correspondents(settings: Settings, page: int = 1, page_size: int = 50) -> dict[str, Any]:
    with client(settings) as http:
        response = http.get(
            "/correspondents/",
            params={"page": page, "page_size": page_size},
        )
        response.raise_for_status()
        return response.json()


def list_all_correspondents(settings: Settings, page_size: int = 200) -> list[dict[str, Any]]:
    page = 1
    items: list[dict[str, Any]] = []
    while True:
        payload = list_correspondents(settings, page=page, page_size=page_size)
        rows = payload.get("results") or []
        items.extend([row for row in rows if isinstance(row, dict)])
        if not payload.get("next"):
            break
        page += 1
    return items


def create_correspondent(settings: Settings, name: str) -> dict[str, Any]:
    payload = {"name": str(name or "").strip()}
    with client(settings) as http:
        response = http.post("/correspondents/", json=payload)
        response.raise_for_status()
        return response.json()


def list_document_types(settings: Settings, page: int = 1, page_size: int = 50) -> dict[str, Any]:
    with client(settings) as http:
        response = http.get(
            "/document_types/",
            params={"page": page, "page_size": page_size},
        )
        response.raise_for_status()
        return response.json()


def get_document_type(settings: Settings, doc_type_id: int) -> dict[str, Any]:
    with client(settings) as http:
        response = http.get(f"/document_types/{doc_type_id}/")
        response.raise_for_status()
        return response.json()


def get_correspondent(settings: Settings, correspondent_id: int) -> dict[str, Any]:
    with client(settings) as http:
        response = http.get(f"/correspondents/{correspondent_id}/")
        response.raise_for_status()
        return response.json()


def get_tag(settings: Settings, tag_id: int) -> dict[str, Any]:
    with client(settings) as http:
        response = http.get(f"/tags/{tag_id}/")
        response.raise_for_status()
        return response.json()


def update_document(settings: Settings, doc_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    with client(settings) as http:
        response = http.patch(f"/documents/{doc_id}/", json=payload)
        response.raise_for_status()
        body = response.json()
    invalidate_document_cache(int(doc_id))
    return body


def add_document_note(settings: Settings, doc_id: int, note: str) -> dict[str, Any]:
    with client(settings) as http:
        response = http.post(f"/documents/{doc_id}/notes/", json={"note": note})
        response.raise_for_status()
        body = response.json()
    invalidate_document_cache(int(doc_id))
    return body


def delete_document_note(settings: Settings, doc_id: int, note_id: int) -> None:
    with client(settings) as http:
        response = http.delete(f"/documents/{doc_id}/notes/", params={"id": note_id})
        response.raise_for_status()
    invalidate_document_cache(int(doc_id))
