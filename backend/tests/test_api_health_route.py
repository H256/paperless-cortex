"""Regression test for issue #123 (AUDIT API-005).

GET /api/health used to be registered on the outer app *after* the ``/api``
sub-app prefix mount, so Starlette routed it into the sub-app (which has no
/health route) and it always 404'd. The route must now be reachable at
/api/health on the outer app and stay open (no API token required).
"""

from __future__ import annotations

import importlib
from typing import Any


def _outer_client(monkeypatch: Any) -> Any:
    """Build a TestClient against a freshly reloaded *outer* app.

    The health route lives on the outer ``app`` (not the ``/api`` sub-app),
    so the probe must be sent to the outer app to be matched.
    """
    monkeypatch.delenv("API_TOKEN", raising=False)
    import app.main as main

    importlib.reload(main)
    from fastapi.testclient import TestClient

    return TestClient(main.app)


def test_api_health_is_reachable_and_open(api_client: Any, monkeypatch: Any) -> None:
    """The outer app serves /api/health with 200 and no credentials required."""
    client = _outer_client(monkeypatch)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_health_not_shadowed_by_api_mount() -> None:
    """The /api sub-app itself has no /health route; only the outer app does.

    Guards against a regression that re-registers the route on the sub-app
    (where it would be shadowed by the prefix mount again) or removes the
    outer-app registration.
    """
    import app.main as main

    importlib.reload(main)
    from fastapi.testclient import TestClient

    # The outer app must expose the route.
    outer = TestClient(main.app)
    assert outer.get("/api/health").status_code == 200
    # The sub-app (what the prefix mount routes to) must NOT expose it.
    sub = TestClient(main.api)
    assert sub.get("/health").status_code == 404
