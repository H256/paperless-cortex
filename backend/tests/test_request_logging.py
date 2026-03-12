from __future__ import annotations

import logging
from typing import Any


def test_status_response_includes_request_and_correlation_ids(api_client: Any) -> None:
    response = api_client.get(
        "/status",
        headers={"X-Request-ID": "req-123", "X-Correlation-ID": "corr-456"},
    )
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req-123"
    assert response.headers["X-Correlation-ID"] == "corr-456"


def test_slow_request_log_includes_request_context(
    api_client: Any,
    monkeypatch: Any,
    caplog: Any,
) -> None:
    import app.main as main

    perf_counter_values = [0.0, 2.0, 2.0, 4.0]

    def _perf_counter() -> float:
        return perf_counter_values.pop(0) if perf_counter_values else 4.0

    monkeypatch.setattr(main.time, "perf_counter", _perf_counter)

    with caplog.at_level(logging.WARNING, logger="app.slow_requests"):
        response = api_client.get(
            "/status",
            headers={"X-Request-ID": "req-slow", "X-Correlation-ID": "corr-slow"},
        )

    assert response.status_code == 200
    slow_record = next(record for record in caplog.records if record.name == "app.slow_requests")
    context = getattr(slow_record, "context", {})
    assert context["service"] == "api"
    assert context["request_id"] == "req-slow"
    assert context["correlation_id"] == "corr-slow"
    assert context["http_method"] == "GET"
    assert context["http_path"] == "/status"
    assert context["status_code"] == 200
    assert context["duration_ms"] == 2000.0
