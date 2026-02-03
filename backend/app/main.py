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
        logging.getLogger(__name__).warning("Meta cache preload failed: %s", exc)
