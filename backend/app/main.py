from __future__ import annotations

import logging
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routes import documents, embeddings, meta, sync, queue, status, chat
from app.config import load_settings
from app.services.meta_cache import refresh_cache
from app.services.meta_sync import sync_correspondents_all, sync_tags_all
from app.db import SessionLocal

app = FastAPI(title="Paperless-NGX Cortex API")

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = FastAPI(title="Paperless-NGX Cortex API")

api.include_router(documents.router)
api.include_router(meta.router)
api.include_router(sync.router)
api.include_router(embeddings.router)
api.include_router(queue.router)
api.include_router(status.router)
api.include_router(chat.router)

app.mount("/api", api)

static_dir_env = os.getenv("FRONTEND_DIST", "")
static_dir = Path(static_dir_env) if static_dir_env else Path(__file__).resolve().parents[2] / "frontend" / "dist"
if static_dir.is_dir():
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.on_event("startup")
def preload_meta_cache() -> None:
    try:
        refresh_cache(load_settings())
    except Exception as exc:
        logging.getLogger(__name__).warning("Meta cache preload failed: %s", exc, exc_info=True)

    settings = load_settings()
    with SessionLocal() as db:
        try:
            total, upserted = sync_tags_all(settings, db)
            logging.getLogger(__name__).info(
                "Startup sync tags total=%s upserted=%s", total, upserted
            )
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "Startup sync tags failed: %s", exc, exc_info=True
            )

        try:
            total, upserted = sync_correspondents_all(settings, db)
            logging.getLogger(__name__).info(
                "Startup sync correspondents total=%s upserted=%s", total, upserted
            )
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "Startup sync correspondents failed: %s", exc, exc_info=True
            )
