from __future__ import annotations

from typing import Any


def _text(exc: Exception) -> str:
    return str(exc).lower()


def classify_worker_error(exc: Exception) -> str:
    message = _text(exc)
    class_name = exc.__class__.__name__.lower()
    if "exceed_context_size_error" in message or "context size" in message:
        return "EMBED_CONTEXT_OVERFLOW"
    if "timeout" in message or "timed out" in message:
        return "LLM_TIMEOUT"
    if "ratelimit" in class_name or "rate limit" in message:
        return "LLM_RATE_LIMIT"
    if "qdrant" in message and ("upsert failed" in message or "status error" in message):
        return "QDRANT_UPSERT_FAIL"
    if "connection" in message or "connect" in message:
        return "NETWORK_CONNECTION_ERROR"
    if "json" in message and "parse" in message:
        return "INVALID_MODEL_OUTPUT"
    return "WORKER_TASK_ERROR"


def is_retryable_error_type(error_type: str) -> bool:
    return error_type in {
        "LLM_TIMEOUT",
        "LLM_RATE_LIMIT",
        "NETWORK_CONNECTION_ERROR",
        "QDRANT_UPSERT_FAIL",
    }


def task_source_from_payload(task: dict[str, Any] | None) -> str | None:
    if not isinstance(task, dict):
        return None
    source = task.get("source")
    if source is None:
        return None
    normalized = str(source).strip()
    return normalized or None
