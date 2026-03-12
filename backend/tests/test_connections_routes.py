from __future__ import annotations

from typing import Any


def test_connections_route_returns_connection_status_items(
    api_client: Any, monkeypatch: Any
) -> None:
    import app.routes.connections as connections_routes

    monkeypatch.setattr(
        connections_routes,
        "run_all",
        lambda _settings: [
            {
                "service": "Paperless",
                "status": "UP",
                "detail": "ok",
                "latency_ms": 12,
            },
            {
                "service": "Qdrant",
                "status": "DOWN",
                "detail": "RuntimeError",
                "latency_ms": 7,
            },
        ],
    )

    response = api_client.get("/connections/")
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert len(payload) == 2
    assert payload[0] == {
        "service": "Paperless",
        "status": "UP",
        "detail": "ok",
        "latency_ms": 12,
    }
    assert payload[1]["service"] == "Qdrant"
    assert payload[1]["status"] == "DOWN"
    assert payload[1]["detail"] == "RuntimeError"
    assert payload[1]["latency_ms"] == 7
