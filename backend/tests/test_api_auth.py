from __future__ import annotations

import importlib
from typing import Any

# /status is self-contained (no Paperless/LLM call) so it is a clean probe of the
# auth gate: it returns 200 when auth is satisfied and 401 when it is not.
PROBE = "/status"


def _client_with_token(monkeypatch: Any, token: str | None) -> Any:
    """Build a TestClient against a freshly reloaded app with the given API_TOKEN.

    Passing ``None`` clears the variable so a prior test's token does not leak.
    """
    if token is None:
        monkeypatch.delenv("API_TOKEN", raising=False)
    else:
        monkeypatch.setenv("API_TOKEN", token)
    import app.main as main

    importlib.reload(main)
    from fastapi.testclient import TestClient

    return TestClient(main.api)


def test_auth_off_by_default_allows_request(api_client: Any, monkeypatch: Any) -> None:
    """When API_TOKEN is unset the /api sub-app stays open (intended posture)."""
    monkeypatch.delenv("API_TOKEN", raising=False)
    response = api_client.get(PROBE)
    assert response.status_code == 200


def test_auth_on_allows_correct_token(api_client: Any, monkeypatch: Any) -> None:
    client = _client_with_token(monkeypatch, "secret-123")
    response = client.get(PROBE, headers={"X-API-Token": "secret-123"})
    assert response.status_code == 200


def test_auth_on_rejects_missing_and_wrong_token(api_client: Any, monkeypatch: Any) -> None:
    client = _client_with_token(monkeypatch, "secret-123")
    assert client.get(PROBE).status_code == 401
    assert client.get(PROBE, headers={"X-API-Token": "wrong"}).status_code == 401
    # Bearer form is also accepted.
    bearer = client.get(PROBE, headers={"Authorization": "Bearer secret-123"})
    assert bearer.status_code == 200
