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
    queue_enabled: bool
    ollama_base_url: str | None
    ollama_model: str | None
    embedding_model: str | None
    qdrant_collection: str | None
    embed_on_sync: bool
    chunk_mode: str
    chunk_max_chars: int
    chunk_overlap: int
    chunk_similarity_threshold: float
    enable_pdf_page_extract: bool
    enable_vision_ocr: bool
    vision_model: str | None
    vision_ocr_prompt: str | None
    vision_ocr_prompt_path: str | None
    suggestions_prompt_path: str | None
    suggestions_debug: bool
    vision_ocr_min_chars: int
    vision_ocr_min_score: int
    vision_ocr_max_non_alnum_ratio: float
    vision_ocr_max_pages: int
    vision_ocr_timeout_seconds: int
    vision_ocr_max_dim: int
    httpx_verify_tls: bool


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
        queue_enabled=os.getenv("QUEUE_ENABLED", "0") == "1",
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
        enable_pdf_page_extract=os.getenv("ENABLE_PDF_PAGE_EXTRACT", "1") == "1",
        enable_vision_ocr=os.getenv("ENABLE_VISION_OCR", "0") == "1",
        vision_model=os.getenv("VISION_MODEL"),
        vision_ocr_prompt=os.getenv("VISION_OCR_PROMPT"),
        vision_ocr_prompt_path=os.getenv("VISION_OCR_PROMPT_PATH"),
        suggestions_prompt_path=os.getenv("SUGGESTIONS_PROMPT_PATH"),
        suggestions_debug=os.getenv("SUGGESTIONS_DEBUG", "0") == "1",
        vision_ocr_min_chars=int(os.getenv("VISION_OCR_MIN_CHARS", "40")),
        vision_ocr_min_score=int(os.getenv("VISION_OCR_MIN_SCORE", "60")),
        vision_ocr_max_non_alnum_ratio=float(
            os.getenv("VISION_OCR_MAX_NONALNUM_RATIO", "0.6")
        ),
        vision_ocr_max_pages=int(os.getenv("VISION_OCR_MAX_PAGES", "0")),
        vision_ocr_timeout_seconds=int(os.getenv("VISION_OCR_TIMEOUT_SECONDS", "120")),
        vision_ocr_max_dim=int(os.getenv("VISION_OCR_MAX_DIM", "1024")),
        httpx_verify_tls=os.getenv("HTTPX_VERIFY_TLS", "1") == "1",
    )
