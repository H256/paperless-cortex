from __future__ import annotations

from typing import Any

from app.config import load_settings
from app.services.ai import ocr_scoring


class FakeClient:
    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.is_closed = False

    def close(self) -> None:
        self.is_closed = True


def test_ocr_scoring_reuses_shared_http_client(monkeypatch: Any) -> None:
    created: list[FakeClient] = []

    def _factory(**kwargs: object) -> FakeClient:
        client = FakeClient(**kwargs)
        created.append(client)
        return client

    monkeypatch.setattr(ocr_scoring.httpx, "Client", _factory)
    settings = load_settings()
    ocr_scoring.clear_client_pool()

    first = ocr_scoring._shared_client(settings, "http://llm.local/v1/completions", 12)
    second = ocr_scoring._shared_client(settings, "http://llm.local/v1/completions", 12)

    assert first is second
    assert len(created) == 1

    ocr_scoring.clear_client_pool()


def test_ocr_scoring_clear_client_pool_closes_clients(monkeypatch: Any) -> None:
    created: list[FakeClient] = []

    def _factory(**kwargs: object) -> FakeClient:
        client = FakeClient(**kwargs)
        created.append(client)
        return client

    monkeypatch.setattr(ocr_scoring.httpx, "Client", _factory)
    settings = load_settings()
    ocr_scoring.clear_client_pool()

    client = ocr_scoring._shared_client(settings, "http://llm.local/v1/completions", 8)

    ocr_scoring.clear_client_pool()

    assert created == [client]
    assert client.is_closed is True
