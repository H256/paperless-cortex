from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off", ""}
_ALLOWED_CHUNK_MODES = {"heuristic", "semantic", "sentence"}
_ALLOWED_VECTOR_PROVIDERS = {"qdrant", "weaviate"}


@dataclass(frozen=True)
class LoggingConfig:
    level: str
    json: bool


@dataclass(frozen=True)
class ApiConfig:
    slow_request_log_ms: int
    status_stream_interval_seconds: int
    status_llm_models_ttl_seconds: int


@dataclass(frozen=True)
class WorkerConfig:
    max_retries: int
    suggestions_max_chars: int


@dataclass(frozen=True)
class PaperlessConfig:
    base_url: str
    api_token: str


@dataclass(frozen=True)
class DatabaseConfig:
    url: str | None


@dataclass(frozen=True)
class QdrantConfig:
    url: str | None
    api_key: str | None
    collection: str | None


@dataclass(frozen=True)
class VectorStoreConfig:
    provider: str
    url: str | None
    api_key: str | None
    collection: str | None
    centroid_collection: str | None


@dataclass(frozen=True)
class WeaviateConfig:
    http_host: str | None
    http_port: int
    http_secure: bool
    grpc_host: str | None
    grpc_port: int
    grpc_secure: bool
    api_key: str | None
    collection: str | None
    centroid_collection: str | None


@dataclass(frozen=True)
class QueueConfig:
    redis_host: str | None
    enabled: bool


@dataclass(frozen=True)
class LlmConfig:
    base_url: str | None
    api_key: str | None
    text_model: str | None
    chat_model: str | None


@dataclass(frozen=True)
class EmbeddingConfig:
    model: str | None
    batch_size: int
    request_timeout_seconds: int
    max_chunks_per_doc: int
    max_input_tokens: int
    embed_on_sync: bool


@dataclass(frozen=True)
class ChunkingConfig:
    mode: str
    max_chars: int
    overlap: int
    similarity_threshold: float


@dataclass(frozen=True)
class VisionConfig:
    enable_pdf_page_extract: bool
    enable_vision_ocr: bool
    model: str | None
    prompt: str | None
    prompt_path: str | None
    min_chars: int
    min_score: int
    max_non_alnum_ratio: float
    max_pages: int
    timeout_seconds: int
    max_dim: int
    target_dim: int
    batch_pages: int
    ocr_chat_base_url: str | None
    ocr_vision_base_url: str | None


@dataclass(frozen=True)
class SuggestionsConfig:
    prompt_path: str | None
    debug: bool
    max_input_chars: int


@dataclass(frozen=True)
class SummaryConfig:
    large_doc_page_threshold: int
    page_notes_timeout_seconds: int
    page_notes_max_output_tokens: int
    summary_section_pages: int
    section_summary_max_input_tokens: int
    section_summary_timeout_seconds: int
    global_summary_max_input_tokens: int
    global_summary_timeout_seconds: int
    summary_max_output_tokens: int


@dataclass(frozen=True)
class HttpConfig:
    verify_tls: bool


@dataclass(frozen=True)
class OcrScoreConfig:
    model: str | None
    threshold_bad: float
    threshold_borderline: float
    enable_logprob_ppl: bool
    ppl_max_prompt_chars: int
    ppl_chunk_chars: int
    ppl_timeout_seconds: int
    vision_timeout_seconds: int
    vision_max_tokens: int


@dataclass(frozen=True)
class EvidenceConfig:
    max_pages: int
    min_snippet_chars: int


@dataclass(frozen=True)
class WritebackConfig:
    execute_enabled: bool


@dataclass(frozen=True)
class FrontendConfig:
    dist_path: str | None


@dataclass(frozen=True)
class DebugConfig:
    llm: bool
    llm_full_response: bool


@dataclass(frozen=True)
class Settings:
    logging: LoggingConfig
    api: ApiConfig
    worker: WorkerConfig
    paperless: PaperlessConfig
    database: DatabaseConfig
    qdrant: QdrantConfig
    vector_store: VectorStoreConfig
    weaviate: WeaviateConfig
    queue: QueueConfig
    llm: LlmConfig
    embeddings: EmbeddingConfig
    chunking: ChunkingConfig
    vision: VisionConfig
    suggestions: SuggestionsConfig
    summary: SummaryConfig
    http: HttpConfig
    ocr_score: OcrScoreConfig
    evidence: EvidenceConfig
    writeback: WritebackConfig
    frontend: FrontendConfig
    debug: DebugConfig

    def __getattr__(self, name: str) -> Any:
        path = _COMPAT_ATTRIBUTE_PATHS.get(name)
        if path is None:
            raise AttributeError(name)
        value: Any = self
        for part in path:
            value = getattr(value, part)
        return value


_COMPAT_ATTRIBUTE_PATHS: dict[str, tuple[str, ...]] = {
    "log_level": ("logging", "level"),
    "log_json": ("logging", "json"),
    "api_slow_request_log_ms": ("api", "slow_request_log_ms"),
    "status_stream_interval_seconds": ("api", "status_stream_interval_seconds"),
    "status_llm_models_ttl_seconds": ("api", "status_llm_models_ttl_seconds"),
    "worker_max_retries": ("worker", "max_retries"),
    "worker_suggestions_max_chars": ("worker", "suggestions_max_chars"),
    "paperless_base_url": ("paperless", "base_url"),
    "paperless_api_token": ("paperless", "api_token"),
    "database_url": ("database", "url"),
    "qdrant_url": ("qdrant", "url"),
    "qdrant_api_key": ("qdrant", "api_key"),
    "qdrant_collection": ("qdrant", "collection"),
    "vector_store_provider": ("vector_store", "provider"),
    "vector_store_url": ("vector_store", "url"),
    "vector_store_api_key": ("vector_store", "api_key"),
    "vector_store_collection": ("vector_store", "collection"),
    "vector_store_centroid_collection": ("vector_store", "centroid_collection"),
    "weaviate_http_host": ("weaviate", "http_host"),
    "weaviate_http_port": ("weaviate", "http_port"),
    "weaviate_http_secure": ("weaviate", "http_secure"),
    "weaviate_grpc_host": ("weaviate", "grpc_host"),
    "weaviate_grpc_port": ("weaviate", "grpc_port"),
    "weaviate_grpc_secure": ("weaviate", "grpc_secure"),
    "weaviate_api_key": ("weaviate", "api_key"),
    "weaviate_collection": ("weaviate", "collection"),
    "weaviate_centroid_collection": ("weaviate", "centroid_collection"),
    "redis_host": ("queue", "redis_host"),
    "queue_enabled": ("queue", "enabled"),
    "llm_base_url": ("llm", "base_url"),
    "llm_api_key": ("llm", "api_key"),
    "text_model": ("llm", "text_model"),
    "chat_model": ("llm", "chat_model"),
    "embedding_model": ("embeddings", "model"),
    "embedding_batch_size": ("embeddings", "batch_size"),
    "embedding_request_timeout_seconds": ("embeddings", "request_timeout_seconds"),
    "embedding_max_chunks_per_doc": ("embeddings", "max_chunks_per_doc"),
    "embedding_max_input_tokens": ("embeddings", "max_input_tokens"),
    "embed_on_sync": ("embeddings", "embed_on_sync"),
    "chunk_mode": ("chunking", "mode"),
    "chunk_max_chars": ("chunking", "max_chars"),
    "chunk_overlap": ("chunking", "overlap"),
    "chunk_similarity_threshold": ("chunking", "similarity_threshold"),
    "enable_pdf_page_extract": ("vision", "enable_pdf_page_extract"),
    "enable_vision_ocr": ("vision", "enable_vision_ocr"),
    "vision_model": ("vision", "model"),
    "vision_ocr_prompt": ("vision", "prompt"),
    "vision_ocr_prompt_path": ("vision", "prompt_path"),
    "vision_ocr_min_chars": ("vision", "min_chars"),
    "vision_ocr_min_score": ("vision", "min_score"),
    "vision_ocr_max_non_alnum_ratio": ("vision", "max_non_alnum_ratio"),
    "vision_ocr_max_pages": ("vision", "max_pages"),
    "vision_ocr_timeout_seconds": ("vision", "timeout_seconds"),
    "vision_ocr_max_dim": ("vision", "max_dim"),
    "vision_ocr_target_dim": ("vision", "target_dim"),
    "vision_ocr_batch_pages": ("vision", "batch_pages"),
    "ocr_chat_base_url": ("vision", "ocr_chat_base_url"),
    "ocr_vision_base_url": ("vision", "ocr_vision_base_url"),
    "suggestions_prompt_path": ("suggestions", "prompt_path"),
    "suggestions_debug": ("suggestions", "debug"),
    "suggestions_max_input_chars": ("suggestions", "max_input_chars"),
    "large_doc_page_threshold": ("summary", "large_doc_page_threshold"),
    "page_notes_timeout_seconds": ("summary", "page_notes_timeout_seconds"),
    "page_notes_max_output_tokens": ("summary", "page_notes_max_output_tokens"),
    "summary_section_pages": ("summary", "summary_section_pages"),
    "section_summary_max_input_tokens": ("summary", "section_summary_max_input_tokens"),
    "section_summary_timeout_seconds": ("summary", "section_summary_timeout_seconds"),
    "global_summary_max_input_tokens": ("summary", "global_summary_max_input_tokens"),
    "global_summary_timeout_seconds": ("summary", "global_summary_timeout_seconds"),
    "summary_max_output_tokens": ("summary", "summary_max_output_tokens"),
    "httpx_verify_tls": ("http", "verify_tls"),
    "ocr_score_model": ("ocr_score", "model"),
    "ocr_score_threshold_bad": ("ocr_score", "threshold_bad"),
    "ocr_score_threshold_borderline": ("ocr_score", "threshold_borderline"),
    "ocr_score_enable_logprob_ppl": ("ocr_score", "enable_logprob_ppl"),
    "ocr_score_ppl_max_prompt_chars": ("ocr_score", "ppl_max_prompt_chars"),
    "ocr_score_ppl_chunk_chars": ("ocr_score", "ppl_chunk_chars"),
    "ocr_score_ppl_timeout_seconds": ("ocr_score", "ppl_timeout_seconds"),
    "ocr_score_vision_timeout_seconds": ("ocr_score", "vision_timeout_seconds"),
    "ocr_score_vision_max_tokens": ("ocr_score", "vision_max_tokens"),
    "evidence_max_pages": ("evidence", "max_pages"),
    "evidence_min_snippet_chars": ("evidence", "min_snippet_chars"),
    "writeback_execute_enabled": ("writeback", "execute_enabled"),
    "frontend_dist": ("frontend", "dist_path"),
    "llm_debug": ("debug", "llm"),
    "llm_debug_full_response": ("debug", "llm_full_response"),
}


def _env_optional_str(name: str) -> str | None:
    raw = os.getenv(name)
    if raw is None:
        return None
    value = raw.strip()
    return value or None


def _env_str(name: str, default: str = "") -> str:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    raise ValueError(f"Invalid boolean for {name}: {raw}")


def _env_int(name: str, default: int, *, min_value: int | None = None) -> int:
    raw = os.getenv(name)
    value = default if raw is None or not raw.strip() else int(raw)
    if min_value is not None and value < min_value:
        raise ValueError(f"{name} must be >= {min_value}")
    return value


def _env_float(name: str, default: float, *, min_value: float | None = None) -> float:
    raw = os.getenv(name)
    value = default if raw is None or not raw.strip() else float(raw)
    if min_value is not None and value < min_value:
        raise ValueError(f"{name} must be >= {min_value}")
    return value


def _normalize_database_url(database_url: str | None) -> str | None:
    if database_url and database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)
    return database_url


def _load_env(repo_root: Path) -> None:
    load_dotenv(repo_root / ".env")


def _build_vector_configs() -> tuple[QdrantConfig, WeaviateConfig, VectorStoreConfig]:
    vector_store_provider = (_env_str("VECTOR_STORE_PROVIDER", "qdrant") or "qdrant").strip().lower()
    if vector_store_provider not in _ALLOWED_VECTOR_PROVIDERS:
        raise ValueError(f"Invalid VECTOR_STORE_PROVIDER: {vector_store_provider}")

    qdrant = QdrantConfig(
        url=_env_optional_str("QDRANT_URL"),
        api_key=_env_optional_str("QDRANT_API_KEY"),
        collection=_env_str("QDRANT_COLLECTION", "paperless_chunks"),
    )

    weaviate_http_host = _env_optional_str("WEAVIATE_HTTP_HOST")
    weaviate_http_port = _env_int("WEAVIATE_HTTP_PORT", 8080, min_value=1)
    weaviate_http_secure = _env_bool("WEAVIATE_HTTP_SECURE", False)
    weaviate_grpc_host = _env_optional_str("WEAVIATE_GRPC_HOST") or weaviate_http_host
    weaviate_grpc_port = _env_int("WEAVIATE_GRPC_PORT", 50051, min_value=1)
    weaviate_grpc_secure = _env_bool("WEAVIATE_GRPC_SECURE", False)
    weaviate_collection = _env_optional_str("WEAVIATE_COLLECTION") or _env_optional_str(
        "VECTOR_STORE_COLLECTION"
    ) or qdrant.collection
    weaviate_centroid_collection = _env_optional_str(
        "WEAVIATE_CENTROID_COLLECTION"
    ) or _env_optional_str("VECTOR_STORE_CENTROID_COLLECTION")

    weaviate = WeaviateConfig(
        http_host=weaviate_http_host,
        http_port=weaviate_http_port,
        http_secure=weaviate_http_secure,
        grpc_host=weaviate_grpc_host,
        grpc_port=weaviate_grpc_port,
        grpc_secure=weaviate_grpc_secure,
        api_key=_env_optional_str("WEAVIATE_API_KEY"),
        collection=weaviate_collection,
        centroid_collection=weaviate_centroid_collection
        or (f"{weaviate_collection}_centroids" if weaviate_collection else None),
    )

    default_vector_store_url = qdrant.url
    default_vector_store_api_key = qdrant.api_key
    default_vector_store_collection = qdrant.collection
    default_vector_store_centroid_collection = (
        f"{qdrant.collection}_centroids" if qdrant.collection else None
    )
    if vector_store_provider == "weaviate":
        protocol = "https" if weaviate.http_secure else "http"
        default_vector_store_url = (
            f"{protocol}://{weaviate.http_host}:{weaviate.http_port}"
            if weaviate.http_host
            else None
        )
        default_vector_store_api_key = weaviate.api_key
        default_vector_store_collection = weaviate.collection
        default_vector_store_centroid_collection = weaviate.centroid_collection

    vector_store = VectorStoreConfig(
        provider=vector_store_provider,
        url=_env_optional_str("VECTOR_STORE_URL") or default_vector_store_url,
        api_key=_env_optional_str("VECTOR_STORE_API_KEY") or default_vector_store_api_key,
        collection=_env_optional_str("VECTOR_STORE_COLLECTION") or default_vector_store_collection,
        centroid_collection=_env_optional_str("VECTOR_STORE_CENTROID_COLLECTION")
        or default_vector_store_centroid_collection,
    )
    return qdrant, weaviate, vector_store


def _validate_settings(settings: Settings) -> None:
    if settings.queue.enabled and not settings.queue.redis_host:
        raise ValueError("REDIS_HOST must be set when QUEUE_ENABLED is true")
    if (
        settings.vector_store.provider == "weaviate"
        and not settings.weaviate.http_host
        and not settings.vector_store.url
    ):
        raise ValueError(
            "WEAVIATE_HTTP_HOST or VECTOR_STORE_URL must be set for VECTOR_STORE_PROVIDER=weaviate"
        )
    if settings.debug.llm_full_response and not settings.debug.llm:
        object.__setattr__(settings, "debug", DebugConfig(llm=True, llm_full_response=True))


def load_settings() -> Settings:
    repo_root = Path(__file__).resolve().parents[2]
    _load_env(repo_root)

    paperless = PaperlessConfig(
        base_url=_env_str("PAPERLESS_BASE_URL", "").rstrip("/"),
        api_token=_env_str("PAPERLESS_API_TOKEN", ""),
    )
    chunk_mode = _env_str("CHUNK_MODE", "heuristic").strip().lower() or "heuristic"
    if chunk_mode not in _ALLOWED_CHUNK_MODES:
        raise ValueError(f"Invalid CHUNK_MODE: {chunk_mode}")

    qdrant, weaviate, vector_store = _build_vector_configs()

    settings = Settings(
        logging=LoggingConfig(
            level=(_env_str("LOG_LEVEL", "INFO") or "INFO").upper(),
            json=_env_bool("LOG_JSON", False),
        ),
        api=ApiConfig(
            slow_request_log_ms=max(0, _env_int("API_SLOW_REQUEST_LOG_MS", 1200)),
            status_stream_interval_seconds=_env_int("STATUS_STREAM_INTERVAL_SECONDS", 5),
            status_llm_models_ttl_seconds=_env_int("STATUS_LLM_MODELS_TTL_SECONDS", 60),
        ),
        worker=WorkerConfig(
            max_retries=max(0, _env_int("WORKER_MAX_RETRIES", 2)),
            suggestions_max_chars=max(500, _env_int("WORKER_SUGGESTIONS_MAX_CHARS", 12000)),
        ),
        paperless=paperless,
        database=DatabaseConfig(url=_normalize_database_url(_env_optional_str("DATABASE_URL"))),
        qdrant=qdrant,
        vector_store=vector_store,
        weaviate=weaviate,
        queue=QueueConfig(
            redis_host=_env_optional_str("REDIS_HOST"),
            enabled=_env_bool("QUEUE_ENABLED", False),
        ),
        llm=LlmConfig(
            base_url=_env_optional_str("LLM_BASE_URL"),
            api_key=_env_optional_str("LLM_API_KEY"),
            text_model=_env_optional_str("TEXT_MODEL"),
            chat_model=_env_optional_str("CHAT_MODEL"),
        ),
        embeddings=EmbeddingConfig(
            model=_env_optional_str("EMBEDDING_MODEL"),
            batch_size=max(1, _env_int("EMBEDDING_BATCH_SIZE", 16)),
            request_timeout_seconds=max(1, _env_int("EMBEDDING_TIMEOUT_SECONDS", 60)),
            max_chunks_per_doc=max(0, _env_int("EMBEDDING_MAX_CHUNKS_PER_DOC", 0)),
            max_input_tokens=max(256, _env_int("EMBEDDING_MAX_INPUT_TOKENS", 3000)),
            embed_on_sync=_env_bool("EMBED_ON_SYNC", False),
        ),
        chunking=ChunkingConfig(
            mode=chunk_mode,
            max_chars=_env_int("CHUNK_MAX_CHARS", 1200),
            overlap=_env_int("CHUNK_OVERLAP", 200),
            similarity_threshold=_env_float("CHUNK_SIMILARITY_THRESHOLD", 0.75),
        ),
        vision=VisionConfig(
            enable_pdf_page_extract=_env_bool("ENABLE_PDF_PAGE_EXTRACT", True),
            enable_vision_ocr=_env_bool("ENABLE_VISION_OCR", False),
            model=_env_optional_str("VISION_MODEL"),
            prompt=_env_optional_str("VISION_OCR_PROMPT"),
            prompt_path=_env_optional_str("VISION_OCR_PROMPT_PATH"),
            min_chars=_env_int("VISION_OCR_MIN_CHARS", 40),
            min_score=_env_int("VISION_OCR_MIN_SCORE", 60),
            max_non_alnum_ratio=_env_float("VISION_OCR_MAX_NONALNUM_RATIO", 0.6),
            max_pages=max(0, _env_int("VISION_OCR_MAX_PAGES", 0)),
            timeout_seconds=_env_int("VISION_OCR_TIMEOUT_SECONDS", 120),
            max_dim=_env_int("VISION_OCR_MAX_DIM", 1024),
            target_dim=max(0, _env_int("VISION_OCR_TARGET_DIM", 0)),
            batch_pages=max(1, _env_int("VISION_OCR_BATCH_PAGES", 1)),
            ocr_chat_base_url=_env_optional_str("OCR_CHAT_BASE"),
            ocr_vision_base_url=_env_optional_str("OCR_VISION_BASE"),
        ),
        suggestions=SuggestionsConfig(
            prompt_path=_env_optional_str("SUGGESTIONS_PROMPT_PATH"),
            debug=_env_bool("SUGGESTIONS_DEBUG", False),
            max_input_chars=max(500, _env_int("SUGGESTIONS_MAX_INPUT_CHARS", 12000)),
        ),
        summary=SummaryConfig(
            large_doc_page_threshold=max(1, _env_int("LARGE_DOC_PAGE_THRESHOLD", 20)),
            page_notes_timeout_seconds=max(5, _env_int("PAGE_NOTES_TIMEOUT_SECONDS", 45)),
            page_notes_max_output_tokens=max(64, _env_int("PAGE_NOTES_MAX_OUTPUT_TOKENS", 300)),
            summary_section_pages=max(2, _env_int("SUMMARY_SECTION_PAGES", 25)),
            section_summary_max_input_tokens=max(
                1000, _env_int("SECTION_SUMMARY_MAX_INPUT_TOKENS", 6000)
            ),
            section_summary_timeout_seconds=max(
                10, _env_int("SECTION_SUMMARY_TIMEOUT_SECONDS", 90)
            ),
            global_summary_max_input_tokens=max(
                1000, _env_int("GLOBAL_SUMMARY_MAX_INPUT_TOKENS", 7000)
            ),
            global_summary_timeout_seconds=max(
                10, _env_int("GLOBAL_SUMMARY_TIMEOUT_SECONDS", 120)
            ),
            summary_max_output_tokens=max(128, _env_int("SUMMARY_MAX_OUTPUT_TOKENS", 900)),
        ),
        http=HttpConfig(verify_tls=_env_bool("HTTPX_VERIFY_TLS", True)),
        ocr_score=OcrScoreConfig(
            model=_env_optional_str("OCR_SCORE_MODEL"),
            threshold_bad=_env_float("OCR_THRESH_BAD", 55.0),
            threshold_borderline=_env_float("OCR_THRESH_BORDERLINE", 32.0),
            enable_logprob_ppl=_env_bool("OCR_ENABLE_LOGPROB_PPL", True),
            ppl_max_prompt_chars=_env_int("OCR_PPL_MAX_PROMPT_CHARS", 20000),
            ppl_chunk_chars=_env_int("OCR_PPL_CHUNK_CHARS", 4000),
            ppl_timeout_seconds=_env_int("OCR_PPL_TIMEOUT_SEC", 120),
            vision_timeout_seconds=_env_int("OCR_VISION_TIMEOUT_SEC", 180),
            vision_max_tokens=_env_int("OCR_VISION_MAX_TOKENS", 1200),
        ),
        evidence=EvidenceConfig(
            max_pages=max(1, _env_int("EVIDENCE_MAX_PAGES", 3)),
            min_snippet_chars=max(1, _env_int("EVIDENCE_MIN_SNIPPET_CHARS", 20)),
        ),
        writeback=WritebackConfig(
            execute_enabled=_env_bool("WRITEBACK_EXECUTE_ENABLED", False),
        ),
        frontend=FrontendConfig(dist_path=_env_optional_str("FRONTEND_DIST")),
        debug=DebugConfig(
            llm=_env_bool("LLM_DEBUG", False),
            llm_full_response=_env_bool("LLM_DEBUG_FULL_RESPONSE", False),
        ),
    )
    _validate_settings(settings)
    return settings
