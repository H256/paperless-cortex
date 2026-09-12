from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from app.config import load_settings
from app.services.search import qdrant
from app.services.search.similarity import fetch_doc_point_vector

if TYPE_CHECKING:
    from pytest import MonkeyPatch


class _FakeRetrieveClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __enter__(self) -> _FakeRetrieveClient:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def post(self, url: str, headers: object = None, json: object = None) -> httpx.Response:
        self.calls.append(url)
        return httpx.Response(404, request=httpx.Request("POST", url))


def test_fetch_doc_point_vector_returns_none_when_retrieve_404_via_real_adapter(
    monkeypatch: MonkeyPatch,
) -> None:
    settings = load_settings()
    # Dispatch assumption: default VECTOR_STORE_PROVIDER is "qdrant" (config.py);
    # this test must go through the real qdrant adapter, not a stub.
    assert settings.vector_store.provider == "qdrant"
    fake = _FakeRetrieveClient()
    monkeypatch.setattr(qdrant, "base_url", lambda _settings: "http://qdrant")
    monkeypatch.setattr(qdrant, "collection_name", lambda _settings: "test")
    monkeypatch.setattr(qdrant, "headers", lambda _settings: {})
    monkeypatch.setattr(qdrant, "client", lambda _settings, timeout: fake)

    assert fetch_doc_point_vector(settings, 123) is None
    assert fake.calls == ["http://qdrant/collections/test/points/retrieve"]


def test_fetch_doc_point_vector_handles_qdrant_404(monkeypatch: MonkeyPatch) -> None:
    request = httpx.Request("POST", "http://qdrant/collections/test/points/retrieve")
    response = httpx.Response(404, request=request)

    def _raise_404(*_args: object, **_kwargs: object) -> None:
        raise httpx.HTTPStatusError("not found", request=request, response=response)

    monkeypatch.setattr("app.services.search.similarity.vector_store.retrieve_points", _raise_404)

    assert fetch_doc_point_vector(load_settings(), 123) is None
