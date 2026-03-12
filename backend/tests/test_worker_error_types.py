from __future__ import annotations

from app.exceptions import WorkerError
from app.services.pipeline.error_types import classify_worker_error, is_retryable_error_type


def test_classify_context_overflow_error() -> None:
    err = RuntimeError("request exceeds the available context size")
    assert classify_worker_error(err) == "EMBED_CONTEXT_OVERFLOW"


def test_classify_timeout_error() -> None:
    err = RuntimeError("request timed out while waiting for model")
    error_type = classify_worker_error(err)
    assert error_type == "LLM_TIMEOUT"
    assert is_retryable_error_type(error_type) is True


def test_non_retryable_unknown_error() -> None:
    err = RuntimeError("unexpected validation mismatch")
    error_type = classify_worker_error(err)
    assert error_type == "WORKER_TASK_ERROR"
    assert is_retryable_error_type(error_type) is False


def test_classify_wrapped_worker_error_uses_original_exception() -> None:
    err = WorkerError(
        "task failed",
        task="sync",
        attempt=1,
        original_exception=RuntimeError("request timed out while waiting for model"),
    )
    error_type = classify_worker_error(err)
    assert error_type == "LLM_TIMEOUT"
    assert is_retryable_error_type(error_type) is True
