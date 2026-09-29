"""Auth posture contract tests (issue #172, [AUDIT BT-001]).

The API is intentionally open (single-user, LAN-deployed, no auth layer).
These tests pin that posture so a future auth dependency (APIKeyHeader,
OAuth2PasswordBearer, custom token check) cannot land silently and break
every existing client:

1. Representative GET/POST endpoints must answer without any credentials.
2. No route module may introduce an auth-style dependency.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

# (method, path) pairs spanning the main route modules. Paperless-backed
# endpoints are excluded: they need the external Paperless client, and the
# auth posture is identical for them (no auth dependency is wired anywhere).
_OPEN_ENDPOINTS = [
    ("GET", "/documents/stats"),
    ("GET", "/queue/status"),
    ("POST", "/queue/clear"),
    ("GET", "/status"),
    ("GET", "/settings/model-providers"),
    ("GET", "/connections"),
    ("POST", "/embeddings/cancel"),
]


@pytest.mark.parametrize(("method", "path"), _OPEN_ENDPOINTS)
def test_sensitive_endpoints_answer_without_credentials(
    api_client: Any, method: str, path: str
) -> None:
    """No 401/403 for any request; the open posture is the contract."""
    response = api_client.request(method, path)
    assert response.status_code not in (401, 403), (
        f"{method} {path} returned {response.status_code} without credentials; "
        "the API is intended to be open — if auth is being introduced, "
        "update this contract and the clients together."
    )


def test_no_auth_dependency_in_route_modules(api_client: Any) -> None:
    """Structural guard: no route module wires an auth-style dependency."""
    from app.routes import (
        chat,
        connections,
        documents,
        documents_actions,
        documents_similarity,
        documents_suggestions,
        embeddings,
        meta,
        queue,
        settings,
        status,
        sync,
        writeback_dryrun,
    )

    authish = re.compile(
        r"APIKeyHeader|OAuth2PasswordBearer|Depends\(\s*(verify|check|auth|require|get_current|ensure)",
        re.IGNORECASE,
    )
    offenders = []
    for module in (
        chat,
        connections,
        documents,
        documents_actions,
        documents_similarity,
        documents_suggestions,
        embeddings,
        meta,
        queue,
        settings,
        status,
        sync,
        writeback_dryrun,
    ):
        assert module.__file__ is not None
        source = Path(module.__file__).read_text(encoding="utf-8")
        for line_no, line in enumerate(source.splitlines(), start=1):
            if authish.search(line):
                offenders.append(f"{module.__name__}:{line_no}: {line.strip()}")

    assert not offenders, (
        "Auth-style dependencies detected in route modules; the API is "
        "intended to be open — update the auth contract tests first:\n"
        + "\n".join(offenders)
    )
