from __future__ import annotations

import json
import logging
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.config import Settings

_RESERVED = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
    "message",
    "asctime",
    "context",
}

_LOG_CONTEXT: ContextVar[dict[str, Any] | None] = ContextVar("log_context", default=None)


def get_log_context() -> dict[str, Any]:
    current = _LOG_CONTEXT.get()
    return dict(current) if isinstance(current, dict) else {}


def bind_log_context(**context: Any) -> Token[dict[str, Any] | None]:
    merged = get_log_context()
    for key, value in context.items():
        if value is not None:
            merged[key] = value
    return _LOG_CONTEXT.set(merged)


def reset_log_context(token: Token[dict[str, Any] | None]) -> None:
    _LOG_CONTEXT.reset(token)


def clear_log_context() -> None:
    _LOG_CONTEXT.set(None)


class ContextFilter(logging.Filter):
    def __init__(self, *, service: str) -> None:
        super().__init__()
        self.service = service

    def filter(self, record: logging.LogRecord) -> bool:
        context: dict[str, Any] = {"service": self.service}
        current = get_log_context()
        if current:
            context.update(current)
        record_context = getattr(record, "context", None)
        if isinstance(record_context, dict):
            context.update(record_context)
        record.context = context
        return True


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        context = getattr(record, "context", None)
        if isinstance(context, dict):
            payload.update(context)
        for key, value in record.__dict__.items():
            if key in _RESERVED or key.startswith("_"):
                continue
            payload[key] = value
        if record.exc_info:
            payload["exc_type"] = record.exc_info[0].__name__ if record.exc_info[0] else "Exception"
            payload["exc_message"] = str(record.exc_info[1]) if record.exc_info[1] else ""
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(settings: Settings, *, service: str) -> None:
    level_name = settings.log_level if settings.log_level else "INFO"
    level = getattr(logging, level_name.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)
    for handler in list(root.handlers):
        root.removeHandler(handler)
    handler = logging.StreamHandler()
    handler.addFilter(ContextFilter(service=service))
    if settings.log_json:
        handler.setFormatter(JsonLogFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root.addHandler(handler)
    logging.getLogger(__name__).info(
        "Logging configured",
        extra={"context": {"json": settings.log_json, "level": level_name.upper()}},
    )


def log_event(
    logger: logging.Logger,
    level: int,
    message: str,
    *,
    exc_info: Any = None,
    **context: Any,
) -> None:
    logger.log(level, message, extra={"context": context}, exc_info=exc_info)
