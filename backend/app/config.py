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
    llm_base_url: str | None
    llm_api_key: str | None
    text_model: str | None
    embedding_model: str | None
    embedding_batch_size: int
    embedding_request_timeout_seconds: int
    embedding_max_chunks_per_doc: int
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
    suggestions_max_input_chars: int
    large_doc_page_threshold: int
    page_notes_timeout_seconds: int
    page_notes_max_output_tokens: int
    summary_section_pages: int
    section_summary_timeout_seconds: int
    global_summary_timeout_seconds: int
    summary_max_output_tokens: int
    vision_ocr_min_chars: int
    vision_ocr_min_score: int
    vision_ocr_max_non_alnum_ratio: float
    vision_ocr_max_pages: int
    vision_ocr_timeout_seconds: int
    vision_ocr_max_dim: int
    vision_ocr_target_dim: int
    vision_ocr_batch_pages: int
    httpx_verify_tls: bool
    ocr_chat_base_url: str | None
    ocr_vision_base_url: str | None
    ocr_score_model: str | None
    ocr_score_threshold_bad: float
    ocr_score_threshold_borderline: float
    ocr_score_enable_logprob_ppl: bool
    ocr_score_ppl_max_prompt_chars: int
    ocr_score_ppl_chunk_chars: int
    ocr_score_ppl_timeout_seconds: int
    ocr_score_vision_timeout_seconds: int
    ocr_score_vision_max_tokens: int
    status_stream_interval_seconds: int
    status_llm_models_ttl_seconds: int
    worker_suggestions_max_chars: int


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
        llm_base_url=os.getenv("LLM_BASE_URL"),
        llm_api_key=os.getenv("LLM_API_KEY"),
        text_model=os.getenv("TEXT_MODEL"),
        embedding_model=os.getenv("EMBEDDING_MODEL"),
        embedding_batch_size=max(1, int(os.getenv("EMBEDDING_BATCH_SIZE", "16"))),
        embedding_request_timeout_seconds=max(1, int(os.getenv("EMBEDDING_TIMEOUT_SECONDS", "60"))),
        embedding_max_chunks_per_doc=max(0, int(os.getenv("EMBEDDING_MAX_CHUNKS_PER_DOC", "0"))),
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
        suggestions_max_input_chars=max(500, int(os.getenv("SUGGESTIONS_MAX_INPUT_CHARS", "12000"))),
        large_doc_page_threshold=max(1, int(os.getenv("LARGE_DOC_PAGE_THRESHOLD", "20"))),
        page_notes_timeout_seconds=max(5, int(os.getenv("PAGE_NOTES_TIMEOUT_SECONDS", "45"))),
        page_notes_max_output_tokens=max(64, int(os.getenv("PAGE_NOTES_MAX_OUTPUT_TOKENS", "300"))),
        summary_section_pages=max(2, int(os.getenv("SUMMARY_SECTION_PAGES", "25"))),
        section_summary_timeout_seconds=max(10, int(os.getenv("SECTION_SUMMARY_TIMEOUT_SECONDS", "90"))),
        global_summary_timeout_seconds=max(10, int(os.getenv("GLOBAL_SUMMARY_TIMEOUT_SECONDS", "120"))),
        summary_max_output_tokens=max(128, int(os.getenv("SUMMARY_MAX_OUTPUT_TOKENS", "900"))),
        vision_ocr_min_chars=int(os.getenv("VISION_OCR_MIN_CHARS", "40")),
        vision_ocr_min_score=int(os.getenv("VISION_OCR_MIN_SCORE", "60")),
        vision_ocr_max_non_alnum_ratio=float(
            os.getenv("VISION_OCR_MAX_NONALNUM_RATIO", "0.6")
        ),
        vision_ocr_max_pages=int(os.getenv("VISION_OCR_MAX_PAGES", "0")),
        vision_ocr_timeout_seconds=int(os.getenv("VISION_OCR_TIMEOUT_SECONDS", "120")),
        vision_ocr_max_dim=int(os.getenv("VISION_OCR_MAX_DIM", "1024")),
        vision_ocr_target_dim=int(os.getenv("VISION_OCR_TARGET_DIM", "0")),
        vision_ocr_batch_pages=max(1, int(os.getenv("VISION_OCR_BATCH_PAGES", "1"))),
        httpx_verify_tls=os.getenv("HTTPX_VERIFY_TLS", "1") == "1",
        ocr_chat_base_url=os.getenv("OCR_CHAT_BASE"),
        ocr_vision_base_url=os.getenv("OCR_VISION_BASE"),
        ocr_score_model=os.getenv("OCR_SCORE_MODEL"),
        ocr_score_threshold_bad=float(os.getenv("OCR_THRESH_BAD", "55")),
        ocr_score_threshold_borderline=float(os.getenv("OCR_THRESH_BORDERLINE", "32")),
        ocr_score_enable_logprob_ppl=os.getenv("OCR_ENABLE_LOGPROB_PPL", "1") == "1",
        ocr_score_ppl_max_prompt_chars=int(os.getenv("OCR_PPL_MAX_PROMPT_CHARS", "20000")),
        ocr_score_ppl_chunk_chars=int(os.getenv("OCR_PPL_CHUNK_CHARS", "4000")),
        ocr_score_ppl_timeout_seconds=int(os.getenv("OCR_PPL_TIMEOUT_SEC", "120")),
        ocr_score_vision_timeout_seconds=int(os.getenv("OCR_VISION_TIMEOUT_SEC", "180")),
        ocr_score_vision_max_tokens=int(os.getenv("OCR_VISION_MAX_TOKENS", "1200")),
        status_stream_interval_seconds=int(os.getenv("STATUS_STREAM_INTERVAL_SECONDS", "5")),
        status_llm_models_ttl_seconds=int(os.getenv("STATUS_LLM_MODELS_TTL_SECONDS", "60")),
        worker_suggestions_max_chars=max(500, int(os.getenv("WORKER_SUGGESTIONS_MAX_CHARS", "12000"))),
    )
