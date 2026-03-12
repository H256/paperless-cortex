from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from app.config import load_settings
from app.services.search.similarity import fetch_doc_point_vector

if TYPE_CHECKING:
    from pytest import MonkeyPatch


def test_fetch_doc_point_vector_handles_qdrant_404(monkeypatch: MonkeyPatch) -> None:
    request = httpx.Request("POST", "http://qdrant/collections/test/points/retrieve")
    response = httpx.Response(404, request=request)

    def _raise_404(*_args: object, **_kwargs: object) -> None:
        raise httpx.HTTPStatusError("not found", request=request, response=response)

    monkeypatch.setattr("app.services.search.similarity.qdrant.retrieve_points", _raise_404)

    assert fetch_doc_point_vector(load_settings(), 123) is None
