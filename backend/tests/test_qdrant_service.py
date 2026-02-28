from __future__ import annotations

import httpx

from app.config import load_settings
from app.services.search import qdrant


class _FakeClient:
    def __init__(self, responses: list[httpx.Response]):
        self._responses = responses
        self.calls: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def post(self, url: str, headers=None, json=None):  # noqa: ANN001
        self.calls.append(url)
        return self._responses.pop(0)


def test_retrieve_points_falls_back_to_points_endpoint_on_404(monkeypatch):
    settings = load_settings()
    request_retrieve = httpx.Request("POST", "http://qdrant/collections/test/points/retrieve")
    request_points = httpx.Request("POST", "http://qdrant/collections/test/points")
    fake = _FakeClient(
        [
            httpx.Response(404, request=request_retrieve),
            httpx.Response(200, request=request_points, json={"result": []}),
        ]
    )

    monkeypatch.setattr(qdrant, "base_url", lambda _settings: "http://qdrant")
    monkeypatch.setattr(qdrant, "collection_name", lambda _settings: "test")
    monkeypatch.setattr(qdrant, "headers", lambda _settings: {})
    monkeypatch.setattr(qdrant, "client", lambda _settings, timeout: fake)

    payload = qdrant.retrieve_points(settings, [123], with_vector=True, with_payload=False)

    assert payload == {"result": []}
    assert fake.calls == [
        "http://qdrant/collections/test/points/retrieve",
        "http://qdrant/collections/test/points",
    ]


def test_retrieve_points_uses_retrieve_endpoint_when_supported(monkeypatch):
    settings = load_settings()
    request_retrieve = httpx.Request("POST", "http://qdrant/collections/test/points/retrieve")
    fake = _FakeClient([httpx.Response(200, request=request_retrieve, json={"result": [{"id": 1}]})])

    monkeypatch.setattr(qdrant, "base_url", lambda _settings: "http://qdrant")
    monkeypatch.setattr(qdrant, "collection_name", lambda _settings: "test")
    monkeypatch.setattr(qdrant, "headers", lambda _settings: {})
    monkeypatch.setattr(qdrant, "client", lambda _settings, timeout: fake)

    payload = qdrant.retrieve_points(settings, [123], with_vector=True, with_payload=False)

    assert payload == {"result": [{"id": 1}]}
    assert fake.calls == ["http://qdrant/collections/test/points/retrieve"]
