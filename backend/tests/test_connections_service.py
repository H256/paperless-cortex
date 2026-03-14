from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import httpx

from app.services.integrations import connections


def test_check_qdrant_reports_missing_config() -> None:
    settings = SimpleNamespace(
        vector_store=SimpleNamespace(provider="qdrant", url=None, api_key=None, collection=None),
        llm_base_url=None,
    )
    ok, detail = connections.check_vector_store_health(cast("Any", settings))
    assert ok is False
    assert detail == "VECTOR_STORE_URL not set"


def test_check_llm_reports_missing_config() -> None:
    settings = SimpleNamespace(llm_base_url=None)
    ok, detail = connections.check_llm(cast("Any", settings))
    assert ok is False
    assert detail == "LLM_BASE_URL not set"


def test_check_paperless_maps_http_error(monkeypatch: Any) -> None:
    settings = SimpleNamespace()

    def _list_documents(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        request = httpx.Request("GET", "http://paperless/api/documents/")
        raise httpx.ConnectError("unreachable", request=request)

    monkeypatch.setattr(connections.paperless, "list_documents", _list_documents)

    ok, detail = connections.check_paperless(cast("Any", settings))
    assert ok is False
    assert detail == "ConnectError"


def test_run_all_formats_statuses(monkeypatch: Any) -> None:
    settings = SimpleNamespace(
        vector_store=SimpleNamespace(provider="qdrant", url="http://qdrant", api_key=None, collection="docs")
    )
    monkeypatch.setattr(connections, "check_paperless", lambda _settings: (True, "ok"))
    monkeypatch.setattr(connections, "check_vector_store_health", lambda _settings: (False, "RuntimeError"))
    monkeypatch.setattr(connections, "check_llm", lambda _settings: (True, "ok"))

    payload = connections.run_all(cast("Any", settings))

    assert [row["service"] for row in payload] == ["Paperless", "Qdrant", "LLM"]
    assert payload[0]["status"] == "UP"
    assert payload[1]["status"] == "DOWN"
    assert payload[1]["detail"] == "RuntimeError"
    assert all(isinstance(row["latency_ms"], int) for row in payload)
