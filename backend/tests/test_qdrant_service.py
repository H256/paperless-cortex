from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from app.config import load_settings
from app.services.search import qdrant
from app.services.search.vector_backends.qdrant_adapter import qdrant_adapter

if TYPE_CHECKING:
    from pytest import MonkeyPatch


class _FakeClient:
    def __init__(self, responses: list[httpx.Response]):
        self._responses = responses
        self.calls: list[str] = []
        self.bodies: list[object] = []

    def __enter__(self) -> _FakeClient:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def post(
        self, url: str, headers: object = None, json: object = None
    ) -> httpx.Response:
        self.calls.append(url)
        self.bodies.append(json)
        return self._responses.pop(0)


def _patch_qdrant_settings(monkeypatch: MonkeyPatch, fake: _FakeClient) -> None:
    monkeypatch.setattr(qdrant, "base_url", lambda _settings: "http://qdrant")
    monkeypatch.setattr(qdrant, "collection_name", lambda _settings: "test")
    monkeypatch.setattr(qdrant, "headers", lambda _settings: {})
    monkeypatch.setattr(qdrant, "client", lambda _settings, timeout: fake)


def _delete_fake() -> _FakeClient:
    request_delete = httpx.Request("POST", "http://qdrant/collections/test/points/delete")
    return _FakeClient([httpx.Response(200, request=request_delete)])


DELETE_URL = "http://qdrant/collections/test/points/delete"


def test_delete_points_for_doc_expanded_source_uses_any_match(monkeypatch: MonkeyPatch) -> None:
    settings = load_settings()
    fake = _delete_fake()
    _patch_qdrant_settings(monkeypatch, fake)

    qdrant_adapter.delete_points_for_doc(settings, doc_id=7, source=("paperless_ocr", "pdf_text"))

    assert fake.calls == [DELETE_URL]
    assert fake.bodies == [
        {
            "filter": {
                "must": [
                    {"key": "doc_id", "match": {"value": 7}},
                    {"key": "source", "match": {"any": ["paperless_ocr", "pdf_text"]}},
                ]
            }
        }
    ]


def test_delete_points_for_doc_single_source_uses_value_match(monkeypatch: MonkeyPatch) -> None:
    settings = load_settings()
    fake = _delete_fake()
    _patch_qdrant_settings(monkeypatch, fake)

    qdrant_adapter.delete_points_for_doc(settings, doc_id=7, source="vision_ocr")

    assert fake.calls == [DELETE_URL]
    assert fake.bodies == [
        {
            "filter": {
                "must": [
                    {"key": "doc_id", "match": {"value": 7}},
                    {"key": "source", "match": {"value": "vision_ocr"}},
                ]
            }
        }
    ]


def test_delete_points_for_doc_without_source_omits_source_condition(
    monkeypatch: MonkeyPatch,
) -> None:
    settings = load_settings()
    fake = _delete_fake()
    _patch_qdrant_settings(monkeypatch, fake)

    qdrant_adapter.delete_points_for_doc(settings, doc_id=7)

    assert fake.calls == [DELETE_URL]
    assert fake.bodies == [
        {"filter": {"must": [{"key": "doc_id", "match": {"value": 7}}]}}
    ]


def test_delete_points_for_doc_raw_source_passthrough_uses_value_match(
    monkeypatch: MonkeyPatch,
) -> None:
    settings = load_settings()
    fake = _delete_fake()
    _patch_qdrant_settings(monkeypatch, fake)

    qdrant_adapter.delete_points_for_doc(settings, doc_id=7, source="pdf_text")

    assert fake.calls == [DELETE_URL]
    assert fake.bodies == [
        {
            "filter": {
                "must": [
                    {"key": "doc_id", "match": {"value": 7}},
                    {"key": "source", "match": {"value": "pdf_text"}},
                ]
            }
        }
    ]


def test_retrieve_points_falls_back_to_points_endpoint_on_404(monkeypatch: MonkeyPatch) -> None:
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


def test_retrieve_points_uses_retrieve_endpoint_when_supported(
    monkeypatch: MonkeyPatch,
) -> None:
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
