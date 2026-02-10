from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings


def base_url(settings: Settings) -> str | None:
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


def list_correspondents(
    settings: Settings, page: int = 1, page_size: int = 50
) -> dict[str, Any]:
    with client(settings) as http:
        response = http.get(
            "/correspondents/",
            params={"page": page, "page_size": page_size},
        )
        response.raise_for_status()
        return response.json()


def list_document_types(
    settings: Settings, page: int = 1, page_size: int = 50
) -> dict[str, Any]:
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
        return response.json()


def add_document_note(settings: Settings, doc_id: int, note: str) -> dict[str, Any]:
    with client(settings) as http:
        response = http.post(f"/documents/{doc_id}/notes/", json={"note": note})
        response.raise_for_status()
        return response.json()


def delete_document_note(settings: Settings, doc_id: int, note_id: int) -> None:
    with client(settings) as http:
        response = http.delete(f"/documents/{doc_id}/notes/", params={"id": note_id})
        response.raise_for_status()
