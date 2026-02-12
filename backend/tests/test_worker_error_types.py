from __future__ import annotations

from app.services.error_types import classify_worker_error, is_retryable_error_type


def test_classify_context_overflow_error():
    err = RuntimeError("request exceeds the available context size")
    assert classify_worker_error(err) == "EMBED_CONTEXT_OVERFLOW"


def test_classify_timeout_error():
    err = RuntimeError("request timed out while waiting for model")
    error_type = classify_worker_error(err)
    assert error_type == "LLM_TIMEOUT"
    assert is_retryable_error_type(error_type) is True


def test_non_retryable_unknown_error():
    err = RuntimeError("unexpected validation mismatch")
    error_type = classify_worker_error(err)
    assert error_type == "WORKER_TASK_ERROR"
    assert is_retryable_error_type(error_type) is False
