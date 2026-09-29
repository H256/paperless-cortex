"""Regression tests for issue #156 (AUDIT INFRA-012): no CI gate detected drift
between the committed ``backend/openapi.json`` and the actual FastAPI routes.

The committed spec feeds the frontend orval codegen and the Docker frontend
build, so a route change that skips the manual
``python scripts/export_openapi.py`` step silently ships stale TypeScript types.
The new backend-ci step regenerates the spec and fails on ``git diff``; these
tests pin both halves of that contract:

* ``test_backend_ci_has_openapi_drift_gate`` — the CI workflow (and its
  ``.gitea`` mirror) actually contains the regenerate-and-diff step, so a
  future edit that drops it is caught.
* ``test_committed_openapi_spec_matches_routes`` — the committed
  ``openapi.json`` is byte-identical to what the app currently produces
  (``json.dumps(api.openapi(), indent=2)``), i.e. no drift. This is the exact
  comparison the CI gate performs.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GITHUB_CI = REPO_ROOT / ".github" / "workflows" / "backend-ci.yml"
GITEA_CI = REPO_ROOT / ".gitea" / "workflows" / "backend-ci.yml"
OPENAPI_PATH = REPO_ROOT / "backend" / "openapi.json"


def test_backend_ci_has_openapi_drift_gate() -> None:
    for path in (GITHUB_CI, GITEA_CI):
        assert path.exists(), f"missing workflow: {path}"
        text = path.read_text(encoding="utf-8")
        # The gate must both regenerate the spec and fail on any diff.
        assert "scripts/export_openapi.py" in text, (
            f"{path.name} lost the OpenAPI regeneration step"
        )
        assert "git diff --exit-code" in text, (
            f"{path.name} lost the `git diff --exit-code` drift check"
        )


@pytest.fixture()
def app_api() -> object:
    # Import the FastAPI app the same way scripts/export_openapi.py does.
    from app.main import api

    return api


def test_committed_openapi_spec_matches_routes(app_api: object) -> None:
    expected = json.dumps(app_api.openapi(), indent=2)  # type: ignore[union-attr]
    committed = OPENAPI_PATH.read_text(encoding="utf-8")
    assert committed == expected, (
        "backend/openapi.json is out of sync with the routes. "
        "Run `python scripts/export_openapi.py` and commit the result."
    )
