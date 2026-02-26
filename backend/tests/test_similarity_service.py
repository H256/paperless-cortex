from __future__ import annotations

import httpx

from app.config import load_settings
from app.services.similarity import fetch_doc_point_vector


def test_fetch_doc_point_vector_handles_qdrant_404(monkeypatch):
    request = httpx.Request("POST", "http://qdrant/collections/test/points/retrieve")
    response = httpx.Response(404, request=request)

    def _raise_404(*_args, **_kwargs):
        raise httpx.HTTPStatusError("not found", request=request, response=response)

    monkeypatch.setattr("app.services.similarity.qdrant.retrieve_points", _raise_404)

    assert fetch_doc_point_vector(load_settings(), 123) is None
