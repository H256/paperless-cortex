from __future__ import annotations

from typing import Any


def test_tags_route_forwards_pagination(api_client: Any, monkeypatch: Any) -> None:
    import app.routes.meta as meta_routes

    captured: dict[str, int] = {}

    def _list_tags(_settings: Any, *, page: int, page_size: int) -> dict[str, Any]:
        captured["page"] = page
        captured["page_size"] = page_size
        return {
            "count": 1,
            "next": None,
            "previous": None,
            "results": [{"id": 10, "name": "tax"}],
        }

    monkeypatch.setattr(meta_routes.paperless, "list_tags", _list_tags)

    response = api_client.get("/tags", params={"page": 3, "page_size": 15})
    assert response.status_code == 200
    assert response.json()["results"][0]["name"] == "tax"
    assert captured == {"page": 3, "page_size": 15}


def test_correspondents_route_forwards_pagination(api_client: Any, monkeypatch: Any) -> None:
    import app.routes.meta as meta_routes

    captured: dict[str, int] = {}

    def _list_correspondents(_settings: Any, *, page: int, page_size: int) -> dict[str, Any]:
        captured["page"] = page
        captured["page_size"] = page_size
        return {
            "count": 1,
            "next": None,
            "previous": None,
            "results": [{"id": 20, "name": "ACME"}],
        }

    monkeypatch.setattr(meta_routes.paperless, "list_correspondents", _list_correspondents)

    response = api_client.get("/correspondents", params={"page": 2, "page_size": 25})
    assert response.status_code == 200
    assert response.json()["results"][0]["name"] == "ACME"
    assert captured == {"page": 2, "page_size": 25}


def test_document_type_route_returns_single_item(api_client: Any, monkeypatch: Any) -> None:
    import app.routes.meta as meta_routes

    monkeypatch.setattr(
        meta_routes.paperless,
        "get_document_type",
        lambda _settings, doc_type_id: {"id": doc_type_id, "name": "invoice"},
    )

    response = api_client.get("/document-types/30")
    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == 30
    assert payload["name"] == "invoice"
    assert "slug" in payload


def test_correspondent_route_returns_single_item(api_client: Any, monkeypatch: Any) -> None:
    import app.routes.meta as meta_routes

    monkeypatch.setattr(
        meta_routes.paperless,
        "get_correspondent",
        lambda _settings, correspondent_id: {"id": correspondent_id, "name": "ACME"},
    )

    response = api_client.get("/correspondents/20")
    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == 20
    assert payload["name"] == "ACME"
    assert "slug" in payload
