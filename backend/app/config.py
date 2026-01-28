from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    paperless_base_url: str
    paperless_api_token: str
    database_url: str | None
    qdrant_url: str | None
    qdrant_api_key: str | None
    redis_host: str | None
    ollama_base_url: str | None
    ollama_model: str | None
    embedding_model: str | None
    qdrant_collection: str | None
    embed_on_sync: bool
    chunk_mode: str
    chunk_max_chars: int
    chunk_overlap: int
    chunk_similarity_threshold: float


def load_settings() -> Settings:
    repo_root = Path(__file__).resolve().parents[2]
    load_dotenv(repo_root / ".env")
    paperless_base_url = os.getenv("PAPERLESS_BASE_URL", "").rstrip("/")
    paperless_api_token = os.getenv("PAPERLESS_API_TOKEN", "")
    database_url = os.getenv("DATABASE_URL")
    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
    return Settings(
        paperless_base_url=paperless_base_url,
        paperless_api_token=paperless_api_token,
        database_url=database_url,
        qdrant_url=os.getenv("QDRANT_URL"),
        qdrant_api_key=os.getenv("QDRANT_API_KEY"),
        redis_host=os.getenv("REDIS_HOST"),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL"),
        ollama_model=os.getenv("OLLAMA_MODEL"),
        embedding_model=os.getenv("EMBEDDING_MODEL"),
        qdrant_collection=os.getenv("QDRANT_COLLECTION", "paperless_chunks"),
        embed_on_sync=os.getenv("EMBED_ON_SYNC", "0") == "1",
        chunk_mode=os.getenv("CHUNK_MODE", "heuristic"),
        chunk_max_chars=int(os.getenv("CHUNK_MAX_CHARS", "1200")),
        chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "200")),
        chunk_similarity_threshold=float(
            os.getenv("CHUNK_SIMILARITY_THRESHOLD", "0.75")
        ),
    )
