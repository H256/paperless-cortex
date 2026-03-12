from __future__ import annotations

import json
import logging

from app.services.runtime.logging_setup import (
    ContextFilter,
    JsonLogFormatter,
    bind_log_context,
    reset_log_context,
)


def test_context_filter_merges_service_bound_and_explicit_context() -> None:
    logger = logging.getLogger("test.logging")
    record = logger.makeRecord(
        "test.logging",
        logging.INFO,
        __file__,
        10,
        "Structured hello",
        (),
        None,
        extra={"context": {"doc_id": 42}},
    )
    token = bind_log_context(request_id="req-1", correlation_id="corr-1")
    try:
        assert ContextFilter(service="api").filter(record) is True
    finally:
        reset_log_context(token)

    context = getattr(record, "context", {})
    assert context["service"] == "api"
    assert context["request_id"] == "req-1"
    assert context["correlation_id"] == "corr-1"
    assert context["doc_id"] == 42

    payload = json.loads(JsonLogFormatter().format(record))
    assert payload["service"] == "api"
    assert payload["request_id"] == "req-1"
    assert payload["correlation_id"] == "corr-1"
    assert payload["doc_id"] == 42
    assert payload["message"] == "Structured hello"
