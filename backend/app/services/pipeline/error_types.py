from __future__ import annotations

from typing import Any


def _text(exc: Exception) -> str:
    original = getattr(exc, "original_exception", None)
    if isinstance(original, Exception):
        return str(original).lower()
    return str(exc).lower()


ERROR_TYPE_CATALOG: dict[str, dict[str, Any]] = {
    "EMBED_CONTEXT_OVERFLOW": {
        "retryable": False,
        "category": "embedding",
        "description": "Embedding payload exceeded model context window.",
    },
    "LLM_TIMEOUT": {
        "retryable": True,
        "category": "llm",
        "description": "LLM request timed out before completion.",
    },
    "LLM_RATE_LIMIT": {
        "retryable": True,
        "category": "llm",
        "description": "LLM provider rate-limited the request.",
    },
    "QDRANT_UPSERT_FAIL": {
        "retryable": True,
        "category": "vector_store",
        "description": "Qdrant rejected or failed vector upsert.",
    },
    "NETWORK_CONNECTION_ERROR": {
        "retryable": True,
        "category": "network",
        "description": "Network/connection failure to external dependency.",
    },
    "INVALID_MODEL_OUTPUT": {
        "retryable": False,
        "category": "model_output",
        "description": "Model output could not be parsed into expected format.",
    },
    "WORKER_TASK_ERROR": {
        "retryable": False,
        "category": "worker",
        "description": "Unhandled worker task failure.",
    },
}


def classify_worker_error(exc: Exception) -> str:
    """Map a raw worker exception to one stable public error-type code."""
    original = getattr(exc, "original_exception", None)
    candidate = original if isinstance(original, Exception) else exc
    message = _text(candidate)
    class_name = candidate.__class__.__name__.lower()
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
    """Return whether a stable error-type code should be treated as retryable."""
    payload = ERROR_TYPE_CATALOG.get(str(error_type or "").strip())
    return bool(payload.get("retryable")) if isinstance(payload, dict) else False


def get_error_type_details(error_type: str | None) -> dict[str, Any] | None:
    """Return the public metadata payload for one stable error-type code."""
    normalized = str(error_type or "").strip()
    if not normalized:
        return None
    payload = ERROR_TYPE_CATALOG.get(normalized)
    if not isinstance(payload, dict):
        return None
    return {
        "code": normalized,
        "retryable": bool(payload.get("retryable")),
        "category": str(payload.get("category") or "unknown"),
        "description": str(payload.get("description") or ""),
    }


def list_error_type_details() -> list[dict[str, Any]]:
    """Return the full stable error-type catalog sorted by code."""
    items: list[dict[str, Any]] = []
    for code in sorted(ERROR_TYPE_CATALOG.keys()):
        detail = get_error_type_details(code)
        if detail is not None:
            items.append(detail)
    return items


def task_source_from_payload(task: dict[str, Any] | None) -> str | None:
    """Extract and normalize an optional task source from a queue payload."""
    if not isinstance(task, dict):
        return None
    source = task.get("source")
    if source is None:
        return None
    normalized = str(source).strip()
    return normalized or None
