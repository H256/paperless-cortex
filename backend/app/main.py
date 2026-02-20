from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.routes import (
    chat,
    connections,
    documents,
    documents_actions,
    documents_suggestions,
    embeddings,
    meta,
    queue,
    status,
    sync,
    writeback_dryrun,
)
from app.config import load_settings
from app.services.meta_cache import refresh_cache
from app.services.meta_sync import sync_correspondents_all, sync_tags_all
from app.db import SessionLocal
from app.services.logging_setup import configure_logging

SETTINGS = load_settings()

def _run_startup_sync() -> None:
    try:
        refresh_cache(SETTINGS)
    except Exception as exc:
        logging.getLogger(__name__).warning("Meta cache preload failed: %s", exc, exc_info=True)

    with SessionLocal() as db:
        try:
            total, upserted = sync_tags_all(SETTINGS, db)
            logging.getLogger(__name__).info(
                "Startup sync tags total=%s upserted=%s", total, upserted
            )
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "Startup sync tags failed: %s", exc, exc_info=True
            )

        try:
            total, upserted = sync_correspondents_all(SETTINGS, db)
            logging.getLogger(__name__).info(
                "Startup sync correspondents total=%s upserted=%s", total, upserted
            )
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "Startup sync correspondents failed: %s", exc, exc_info=True
            )


@asynccontextmanager
async def _app_lifespan(_app: FastAPI):
    _run_startup_sync()
    yield


configure_logging(SETTINGS, service="api")
app = FastAPI(title="Paperless-NGX Cortex API", lifespan=_app_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = FastAPI(title="Paperless-NGX Cortex API")
slow_request_logger = logging.getLogger("app.slow_requests")


@api.middleware("http")
async def log_slow_requests(request, call_next):
    threshold_ms = SETTINGS.api_slow_request_log_ms
    if threshold_ms <= 0:
        return await call_next(request)

    started = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        if elapsed_ms >= threshold_ms:
            slow_request_logger.warning(
                "Slow request method=%s path=%s status=%s duration_ms=%.1f threshold_ms=%s",
                request.method,
                request.url.path,
                status_code,
                elapsed_ms,
                threshold_ms,
            )

api.include_router(documents.router)
api.include_router(documents_actions.router)
api.include_router(documents_suggestions.router)
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
    async def get_response(self, path: str, scope):
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
