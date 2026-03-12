from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import load_settings
from app.db import SessionLocal
from app.exceptions import ConfigurationError, DocumentNotFoundError, PaperlessIntelligenceError
from app.routes import (
    chat,
    connections,
    documents,
    documents_actions,
    documents_similarity,
    documents_suggestions,
    embeddings,
    meta,
    queue,
    status,
    sync,
    writeback_dryrun,
)
from app.services.integrations.meta_cache import refresh_cache
from app.services.integrations.meta_sync import sync_correspondents_all, sync_tags_all
from app.services.runtime.logging_setup import (
    bind_log_context,
    configure_logging,
    get_log_context,
    log_event,
    reset_log_context,
)
from app.version import API_VERSION

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

SETTINGS = load_settings()
logger = logging.getLogger(__name__)
slow_request_logger = logging.getLogger("app.slow_requests")


def _request_id_from_headers(request: Any) -> tuple[str, str]:
    request_id = str(request.headers.get("x-request-id") or "").strip() or str(uuid4())
    correlation_id = str(request.headers.get("x-correlation-id") or "").strip() or request_id
    return request_id, correlation_id


def _error_code_for_status(status_code: int) -> str:
    if status_code == 400:
        return "BAD_REQUEST"
    if status_code == 401:
        return "UNAUTHORIZED"
    if status_code == 403:
        return "FORBIDDEN"
    if status_code == 404:
        return "NOT_FOUND"
    if status_code == 409:
        return "CONFLICT"
    if status_code == 422:
        return "VALIDATION_ERROR"
    return "INTERNAL_SERVER_ERROR" if status_code >= 500 else "HTTP_ERROR"


def _status_for_domain_error(exc: PaperlessIntelligenceError) -> int:
    if isinstance(exc, DocumentNotFoundError):
        return 404
    if isinstance(exc, ConfigurationError):
        return 500
    return 400


def _error_response_payload(*, detail: Any, error_code: str) -> dict[str, Any]:
    context = get_log_context()
    return {
        "detail": detail,
        "error_code": error_code,
        "request_id": context.get("request_id"),
        "correlation_id": context.get("correlation_id"),
    }


def _error_response(
    *,
    status_code: int,
    detail: Any,
    error_code: str,
) -> JSONResponse:
    response = JSONResponse(
        status_code=status_code,
        content=_error_response_payload(detail=detail, error_code=error_code),
    )
    response.headers["X-Error-Code"] = error_code
    context = get_log_context()
    request_id = context.get("request_id")
    correlation_id = context.get("correlation_id")
    if isinstance(request_id, str) and request_id:
        response.headers["X-Request-ID"] = request_id
    if isinstance(correlation_id, str) and correlation_id:
        response.headers["X-Correlation-ID"] = correlation_id
    return response


def _run_startup_sync() -> None:
    startup_token = bind_log_context(startup_phase="bootstrap")
    try:
        try:
            refresh_cache(SETTINGS)
        except (httpx.HTTPError, RuntimeError, ValueError) as exc:
            log_event(
                logger,
                logging.WARNING,
                "Startup meta cache preload failed",
                exc_info=exc,
                error_class=exc.__class__.__name__,
                error_message=str(exc),
            )

        with SessionLocal() as db:
            try:
                total, upserted = sync_tags_all(SETTINGS, db)
                log_event(logger, logging.INFO, "Startup sync tags completed", total=total, upserted=upserted)
            except (httpx.HTTPError, RuntimeError, ValueError, SQLAlchemyError) as exc:
                log_event(
                    logger,
                    logging.WARNING,
                    "Startup sync tags failed",
                    exc_info=exc,
                    error_class=exc.__class__.__name__,
                    error_message=str(exc),
                )

            try:
                total, upserted = sync_correspondents_all(SETTINGS, db)
                log_event(
                    logger,
                    logging.INFO,
                    "Startup sync correspondents completed",
                    total=total,
                    upserted=upserted,
                )
            except (httpx.HTTPError, RuntimeError, ValueError, SQLAlchemyError) as exc:
                log_event(
                    logger,
                    logging.WARNING,
                    "Startup sync correspondents failed",
                    exc_info=exc,
                    error_class=exc.__class__.__name__,
                    error_message=str(exc),
                )
    finally:
        reset_log_context(startup_token)


@asynccontextmanager
async def _app_lifespan(_app: FastAPI) -> AsyncIterator[None]:
    _run_startup_sync()
    yield


configure_logging(SETTINGS, service="api")
app = FastAPI(title="Paperless-NGX Cortex API", version=API_VERSION, lifespan=_app_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = FastAPI(title="Paperless-NGX Cortex API", version=API_VERSION)


@api.middleware("http")
async def bind_request_logging_context(request: Any, call_next: Any) -> Any:
    request_id, correlation_id = _request_id_from_headers(request)
    token = bind_log_context(
        request_id=request_id,
        correlation_id=correlation_id,
        http_method=request.method,
        http_path=request.url.path,
    )
    threshold_ms = SETTINGS.api_slow_request_log_ms
    started = time.perf_counter()
    status_code = 500
    response: Any | None = None
    try:
        response = await call_next(request)
        status_code = int(response.status_code)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Correlation-ID"] = correlation_id
        return response
    finally:
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        if threshold_ms > 0 and elapsed_ms >= threshold_ms:
            log_event(
                slow_request_logger,
                logging.WARNING,
                "Slow request",
                status_code=status_code,
                duration_ms=round(elapsed_ms, 1),
                threshold_ms=threshold_ms,
            )
        reset_log_context(token)


@api.exception_handler(PaperlessIntelligenceError)
async def handle_domain_error(
    _request: Request, exc: PaperlessIntelligenceError
) -> JSONResponse:
    status_code = _status_for_domain_error(exc)
    log_event(
        logger,
        logging.ERROR if status_code >= 500 else logging.WARNING,
        "Domain error response",
        status_code=status_code,
        error_code=exc.error_code,
        error_message=exc.message,
        error_class=exc.__class__.__name__,
    )
    return _error_response(
        status_code=status_code,
        detail=exc.message,
        error_code=exc.error_code,
    )


@api.exception_handler(StarletteHTTPException)
async def handle_http_error(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    error_code = _error_code_for_status(int(exc.status_code))
    log_event(
        logger,
        logging.WARNING if exc.status_code < 500 else logging.ERROR,
        "HTTP error response",
        status_code=int(exc.status_code),
        error_code=error_code,
        error_message=str(exc.detail),
    )
    return _error_response(
        status_code=int(exc.status_code),
        detail=exc.detail,
        error_code=error_code,
    )


@api.exception_handler(RequestValidationError)
async def handle_validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
    log_event(
        logger,
        logging.WARNING,
        "Request validation error",
        status_code=422,
        error_code="VALIDATION_ERROR",
    )
    return _error_response(
        status_code=422,
        detail=exc.errors(),
        error_code="VALIDATION_ERROR",
    )


api.include_router(documents.router)
api.include_router(documents_actions.router)
api.include_router(documents_suggestions.router)
api.include_router(documents_similarity.router)
api.include_router(meta.router)
api.include_router(sync.router)
api.include_router(embeddings.router)
api.include_router(connections.router)
api.include_router(queue.router)
api.include_router(status.router)
api.include_router(chat.router)
api.include_router(writeback_dryrun.router)

app.mount("/api", api)


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: Any) -> Any:
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404:
                return await super().get_response("index.html", scope)
            raise


static_dir_env = os.getenv("FRONTEND_DIST", "")
static_dir = Path(static_dir_env) if static_dir_env else Path(__file__).resolve().parents[2] / "frontend" / "dist"
if static_dir.is_dir():
    app.mount("/", SPAStaticFiles(directory=static_dir, html=True), name="static")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
