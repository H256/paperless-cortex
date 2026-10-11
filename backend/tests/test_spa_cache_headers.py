from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    # Imported here: importing app.main while the tests are collected would configure the
    # application (logging, settings) before the test fixtures prepare the environment.
    from app.main import SPAStaticFiles

    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>app</html>", encoding="utf-8")
    (dist / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    (dist / "assets" / "index-abc123.js").write_text("console.log(1)", encoding="utf-8")
    app = FastAPI()
    app.mount("/", SPAStaticFiles(directory=dist, html=True), name="static")
    return TestClient(app)


def test_index_html_is_revalidated(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"


def test_spa_fallback_is_revalidated(client: TestClient) -> None:
    response = client.get("/documents/42")
    assert response.status_code == 200
    assert "app" in response.text
    assert response.headers["cache-control"] == "no-cache"


def test_hashed_assets_are_immutable(client: TestClient) -> None:
    response = client.get("/assets/index-abc123.js")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"


def test_other_root_files_are_revalidated(client: TestClient) -> None:
    response = client.get("/favicon.svg")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"


def test_missing_asset_does_not_become_immutable(client: TestClient) -> None:
    response = client.get("/assets/missing.js")
    # unknown paths fall back to the SPA shell and must stay revalidated
    assert response.headers["cache-control"] == "no-cache"
