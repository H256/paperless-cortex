from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off", ""}
_ALLOWED_CHUNK_MODES = {"heuristic", "semantic", "sentence"}


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
class Settings:
    log_level: str
    log_json: bool
    api_slow_request_log_ms: int
    worker_max_retries: int
    paperless_base_url: str
    paperless_api_token: str
    database_url: str | None
    qdrant_url: str | None
    qdrant_api_key: str | None
    vector_store_provider: str
    vector_store_url: str | None
    vector_store_api_key: str | None
    vector_store_collection: str | None
    vector_store_centroid_collection: str | None
    weaviate_http_host: str | None
    weaviate_http_port: int
    weaviate_http_secure: bool
    weaviate_grpc_host: str | None
    weaviate_grpc_port: int
    weaviate_grpc_secure: bool
    weaviate_api_key: str | None
    weaviate_collection: str | None
    weaviate_centroid_collection: str | None
    redis_host: str | None
    queue_enabled: bool
    llm_base_url: str | None
    llm_api_key: str | None
    text_model: str | None
    chat_model: str | None
    embedding_model: str | None
    embedding_batch_size: int
    embedding_request_timeout_seconds: int
    embedding_max_chunks_per_doc: int
    embedding_max_input_tokens: int
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
    section_summary_max_input_tokens: int
    section_summary_timeout_seconds: int
    global_summary_max_input_tokens: int
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
    evidence_max_pages: int
    evidence_min_snippet_chars: int
    worker_suggestions_max_chars: int
    writeback_execute_enabled: bool

    @property
    def logging(self) -> LoggingConfig:
        return LoggingConfig(level=self.log_level, json=self.log_json)

    @property
    def api(self) -> ApiConfig:
        return ApiConfig(
            slow_request_log_ms=self.api_slow_request_log_ms,
            status_stream_interval_seconds=self.status_stream_interval_seconds,
            status_llm_models_ttl_seconds=self.status_llm_models_ttl_seconds,
        )

    @property
    def worker(self) -> WorkerConfig:
        return WorkerConfig(
            max_retries=self.worker_max_retries,
            suggestions_max_chars=self.worker_suggestions_max_chars,
        )

    @property
    def paperless(self) -> PaperlessConfig:
        return PaperlessConfig(base_url=self.paperless_base_url, api_token=self.paperless_api_token)

    @property
    def database(self) -> DatabaseConfig:
        return DatabaseConfig(url=self.database_url)

    @property
    def qdrant(self) -> QdrantConfig:
        return QdrantConfig(
            url=self.qdrant_url,
            api_key=self.qdrant_api_key,
            collection=self.qdrant_collection,
        )

    @property
    def vector_store(self) -> VectorStoreConfig:
        return VectorStoreConfig(
            provider=self.vector_store_provider,
            url=self.vector_store_url,
            api_key=self.vector_store_api_key,
            collection=self.vector_store_collection,
            centroid_collection=self.vector_store_centroid_collection,
        )

    @property
    def queue(self) -> QueueConfig:
        return QueueConfig(redis_host=self.redis_host, enabled=self.queue_enabled)

    @property
    def llm(self) -> LlmConfig:
        return LlmConfig(
            base_url=self.llm_base_url,
            api_key=self.llm_api_key,
            text_model=self.text_model,
            chat_model=self.chat_model,
        )

    @property
    def embeddings(self) -> EmbeddingConfig:
        return EmbeddingConfig(
            model=self.embedding_model,
            batch_size=self.embedding_batch_size,
            request_timeout_seconds=self.embedding_request_timeout_seconds,
            max_chunks_per_doc=self.embedding_max_chunks_per_doc,
            max_input_tokens=self.embedding_max_input_tokens,
            embed_on_sync=self.embed_on_sync,
        )

    @property
    def chunking(self) -> ChunkingConfig:
        return ChunkingConfig(
            mode=self.chunk_mode,
            max_chars=self.chunk_max_chars,
            overlap=self.chunk_overlap,
            similarity_threshold=self.chunk_similarity_threshold,
        )

    @property
    def vision(self) -> VisionConfig:
        return VisionConfig(
            enable_pdf_page_extract=self.enable_pdf_page_extract,
            enable_vision_ocr=self.enable_vision_ocr,
            model=self.vision_model,
            prompt=self.vision_ocr_prompt,
            prompt_path=self.vision_ocr_prompt_path,
            min_chars=self.vision_ocr_min_chars,
            min_score=self.vision_ocr_min_score,
            max_non_alnum_ratio=self.vision_ocr_max_non_alnum_ratio,
            max_pages=self.vision_ocr_max_pages,
            timeout_seconds=self.vision_ocr_timeout_seconds,
            max_dim=self.vision_ocr_max_dim,
            target_dim=self.vision_ocr_target_dim,
            batch_pages=self.vision_ocr_batch_pages,
            ocr_chat_base_url=self.ocr_chat_base_url,
            ocr_vision_base_url=self.ocr_vision_base_url,
        )

    @property
    def suggestions(self) -> SuggestionsConfig:
        return SuggestionsConfig(
            prompt_path=self.suggestions_prompt_path,
            debug=self.suggestions_debug,
            max_input_chars=self.suggestions_max_input_chars,
        )

    @property
    def summary(self) -> SummaryConfig:
        return SummaryConfig(
            large_doc_page_threshold=self.large_doc_page_threshold,
            page_notes_timeout_seconds=self.page_notes_timeout_seconds,
            page_notes_max_output_tokens=self.page_notes_max_output_tokens,
            summary_section_pages=self.summary_section_pages,
            section_summary_max_input_tokens=self.section_summary_max_input_tokens,
            section_summary_timeout_seconds=self.section_summary_timeout_seconds,
            global_summary_max_input_tokens=self.global_summary_max_input_tokens,
            global_summary_timeout_seconds=self.global_summary_timeout_seconds,
            summary_max_output_tokens=self.summary_max_output_tokens,
        )

    @property
    def http(self) -> HttpConfig:
        return HttpConfig(verify_tls=self.httpx_verify_tls)

    @property
    def ocr_score(self) -> OcrScoreConfig:
        return OcrScoreConfig(
            model=self.ocr_score_model,
            threshold_bad=self.ocr_score_threshold_bad,
            threshold_borderline=self.ocr_score_threshold_borderline,
            enable_logprob_ppl=self.ocr_score_enable_logprob_ppl,
            ppl_max_prompt_chars=self.ocr_score_ppl_max_prompt_chars,
            ppl_chunk_chars=self.ocr_score_ppl_chunk_chars,
            ppl_timeout_seconds=self.ocr_score_ppl_timeout_seconds,
            vision_timeout_seconds=self.ocr_score_vision_timeout_seconds,
            vision_max_tokens=self.ocr_score_vision_max_tokens,
        )

    @property
    def evidence(self) -> EvidenceConfig:
        return EvidenceConfig(
            max_pages=self.evidence_max_pages,
            min_snippet_chars=self.evidence_min_snippet_chars,
        )

    @property
    def writeback(self) -> WritebackConfig:
        return WritebackConfig(execute_enabled=self.writeback_execute_enabled)


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


def load_settings() -> Settings:
    repo_root = Path(__file__).resolve().parents[2]
    load_dotenv(repo_root / ".env")
    paperless_base_url = _env_str("PAPERLESS_BASE_URL", "").rstrip("/")
    chunk_mode = _env_str("CHUNK_MODE", "heuristic").strip().lower() or "heuristic"
    if chunk_mode not in _ALLOWED_CHUNK_MODES:
        raise ValueError(f"Invalid CHUNK_MODE: {chunk_mode}")
    database_url = _normalize_database_url(_env_optional_str("DATABASE_URL"))
    vector_store_provider = (_env_str("VECTOR_STORE_PROVIDER", "qdrant") or "qdrant").strip().lower()
    qdrant_url = _env_optional_str("QDRANT_URL")
    qdrant_api_key = _env_optional_str("QDRANT_API_KEY")
    qdrant_collection = _env_str("QDRANT_COLLECTION", "paperless_chunks")
    weaviate_http_host = _env_optional_str("WEAVIATE_HTTP_HOST")
    weaviate_http_port = _env_int("WEAVIATE_HTTP_PORT", 8080, min_value=1)
    weaviate_http_secure = _env_bool("WEAVIATE_HTTP_SECURE", False)
    weaviate_grpc_host = _env_optional_str("WEAVIATE_GRPC_HOST") or weaviate_http_host
    weaviate_grpc_port = _env_int("WEAVIATE_GRPC_PORT", 50051, min_value=1)
    weaviate_grpc_secure = _env_bool("WEAVIATE_GRPC_SECURE", False)
    weaviate_api_key = _env_optional_str("WEAVIATE_API_KEY")
    weaviate_collection = _env_optional_str("WEAVIATE_COLLECTION") or _env_optional_str(
        "VECTOR_STORE_COLLECTION"
    ) or qdrant_collection
    weaviate_centroid_collection = _env_optional_str(
        "WEAVIATE_CENTROID_COLLECTION"
    ) or _env_optional_str("VECTOR_STORE_CENTROID_COLLECTION")
    default_vector_store_url = qdrant_url
    default_vector_store_api_key = qdrant_api_key
    default_vector_store_collection = qdrant_collection
    default_vector_store_centroid_collection = (
        f"{qdrant_collection}_centroids" if qdrant_collection else None
    )
    if vector_store_provider == "weaviate":
        protocol = "https" if weaviate_http_secure else "http"
        default_vector_store_url = (
            f"{protocol}://{weaviate_http_host}:{weaviate_http_port}" if weaviate_http_host else None
        )
        default_vector_store_api_key = weaviate_api_key
        default_vector_store_collection = weaviate_collection
        default_vector_store_centroid_collection = (
            weaviate_centroid_collection
            or (f"{weaviate_collection}_centroids" if weaviate_collection else None)
        )
    vector_store_url = _env_optional_str("VECTOR_STORE_URL") or default_vector_store_url
    vector_store_api_key = _env_optional_str("VECTOR_STORE_API_KEY") or default_vector_store_api_key
    vector_store_collection = _env_optional_str("VECTOR_STORE_COLLECTION") or default_vector_store_collection
    vector_store_centroid_collection = _env_optional_str(
        "VECTOR_STORE_CENTROID_COLLECTION"
    ) or default_vector_store_centroid_collection
    return Settings(
        log_level=(_env_str("LOG_LEVEL", "INFO") or "INFO").upper(),
        log_json=_env_bool("LOG_JSON", False),
        api_slow_request_log_ms=max(0, _env_int("API_SLOW_REQUEST_LOG_MS", 1200)),
        worker_max_retries=max(0, _env_int("WORKER_MAX_RETRIES", 2)),
        paperless_base_url=paperless_base_url,
        paperless_api_token=_env_str("PAPERLESS_API_TOKEN", ""),
        database_url=database_url,
        qdrant_url=qdrant_url,
        qdrant_api_key=qdrant_api_key,
        vector_store_provider=vector_store_provider,
        vector_store_url=vector_store_url,
        vector_store_api_key=vector_store_api_key,
        vector_store_collection=vector_store_collection,
        vector_store_centroid_collection=vector_store_centroid_collection,
        weaviate_http_host=weaviate_http_host,
        weaviate_http_port=weaviate_http_port,
        weaviate_http_secure=weaviate_http_secure,
        weaviate_grpc_host=weaviate_grpc_host,
        weaviate_grpc_port=weaviate_grpc_port,
        weaviate_grpc_secure=weaviate_grpc_secure,
        weaviate_api_key=weaviate_api_key,
        weaviate_collection=weaviate_collection,
        weaviate_centroid_collection=weaviate_centroid_collection
        or (f"{weaviate_collection}_centroids" if weaviate_collection else None),
        redis_host=_env_optional_str("REDIS_HOST"),
        queue_enabled=_env_bool("QUEUE_ENABLED", False),
        llm_base_url=_env_optional_str("LLM_BASE_URL"),
        llm_api_key=_env_optional_str("LLM_API_KEY"),
        text_model=_env_optional_str("TEXT_MODEL"),
        chat_model=_env_optional_str("CHAT_MODEL"),
        embedding_model=_env_optional_str("EMBEDDING_MODEL"),
        embedding_batch_size=max(1, _env_int("EMBEDDING_BATCH_SIZE", 16)),
        embedding_request_timeout_seconds=max(1, _env_int("EMBEDDING_TIMEOUT_SECONDS", 60)),
        embedding_max_chunks_per_doc=max(0, _env_int("EMBEDDING_MAX_CHUNKS_PER_DOC", 0)),
        embedding_max_input_tokens=max(256, _env_int("EMBEDDING_MAX_INPUT_TOKENS", 3000)),
        qdrant_collection=qdrant_collection,
        embed_on_sync=_env_bool("EMBED_ON_SYNC", False),
        chunk_mode=chunk_mode,
        chunk_max_chars=_env_int("CHUNK_MAX_CHARS", 1200),
        chunk_overlap=_env_int("CHUNK_OVERLAP", 200),
        chunk_similarity_threshold=_env_float("CHUNK_SIMILARITY_THRESHOLD", 0.75),
        enable_pdf_page_extract=_env_bool("ENABLE_PDF_PAGE_EXTRACT", True),
        enable_vision_ocr=_env_bool("ENABLE_VISION_OCR", False),
        vision_model=_env_optional_str("VISION_MODEL"),
        vision_ocr_prompt=_env_optional_str("VISION_OCR_PROMPT"),
        vision_ocr_prompt_path=_env_optional_str("VISION_OCR_PROMPT_PATH"),
        suggestions_prompt_path=_env_optional_str("SUGGESTIONS_PROMPT_PATH"),
        suggestions_debug=_env_bool("SUGGESTIONS_DEBUG", False),
        suggestions_max_input_chars=max(500, _env_int("SUGGESTIONS_MAX_INPUT_CHARS", 12000)),
        large_doc_page_threshold=max(1, _env_int("LARGE_DOC_PAGE_THRESHOLD", 20)),
        page_notes_timeout_seconds=max(5, _env_int("PAGE_NOTES_TIMEOUT_SECONDS", 45)),
        page_notes_max_output_tokens=max(64, _env_int("PAGE_NOTES_MAX_OUTPUT_TOKENS", 300)),
        summary_section_pages=max(2, _env_int("SUMMARY_SECTION_PAGES", 25)),
        section_summary_max_input_tokens=max(1000, _env_int("SECTION_SUMMARY_MAX_INPUT_TOKENS", 6000)),
        section_summary_timeout_seconds=max(10, _env_int("SECTION_SUMMARY_TIMEOUT_SECONDS", 90)),
        global_summary_max_input_tokens=max(1000, _env_int("GLOBAL_SUMMARY_MAX_INPUT_TOKENS", 7000)),
        global_summary_timeout_seconds=max(10, _env_int("GLOBAL_SUMMARY_TIMEOUT_SECONDS", 120)),
        summary_max_output_tokens=max(128, _env_int("SUMMARY_MAX_OUTPUT_TOKENS", 900)),
        vision_ocr_min_chars=_env_int("VISION_OCR_MIN_CHARS", 40),
        vision_ocr_min_score=_env_int("VISION_OCR_MIN_SCORE", 60),
        vision_ocr_max_non_alnum_ratio=_env_float("VISION_OCR_MAX_NONALNUM_RATIO", 0.6),
        vision_ocr_max_pages=max(0, _env_int("VISION_OCR_MAX_PAGES", 0)),
        vision_ocr_timeout_seconds=_env_int("VISION_OCR_TIMEOUT_SECONDS", 120),
        vision_ocr_max_dim=_env_int("VISION_OCR_MAX_DIM", 1024),
        vision_ocr_target_dim=max(0, _env_int("VISION_OCR_TARGET_DIM", 0)),
        vision_ocr_batch_pages=max(1, _env_int("VISION_OCR_BATCH_PAGES", 1)),
        httpx_verify_tls=_env_bool("HTTPX_VERIFY_TLS", True),
        ocr_chat_base_url=_env_optional_str("OCR_CHAT_BASE"),
        ocr_vision_base_url=_env_optional_str("OCR_VISION_BASE"),
        ocr_score_model=_env_optional_str("OCR_SCORE_MODEL"),
        ocr_score_threshold_bad=_env_float("OCR_THRESH_BAD", 55.0),
        ocr_score_threshold_borderline=_env_float("OCR_THRESH_BORDERLINE", 32.0),
        ocr_score_enable_logprob_ppl=_env_bool("OCR_ENABLE_LOGPROB_PPL", True),
        ocr_score_ppl_max_prompt_chars=_env_int("OCR_PPL_MAX_PROMPT_CHARS", 20000),
        ocr_score_ppl_chunk_chars=_env_int("OCR_PPL_CHUNK_CHARS", 4000),
        ocr_score_ppl_timeout_seconds=_env_int("OCR_PPL_TIMEOUT_SEC", 120),
        ocr_score_vision_timeout_seconds=_env_int("OCR_VISION_TIMEOUT_SEC", 180),
        ocr_score_vision_max_tokens=_env_int("OCR_VISION_MAX_TOKENS", 1200),
        status_stream_interval_seconds=_env_int("STATUS_STREAM_INTERVAL_SECONDS", 5),
        status_llm_models_ttl_seconds=_env_int("STATUS_LLM_MODELS_TTL_SECONDS", 60),
        evidence_max_pages=max(1, _env_int("EVIDENCE_MAX_PAGES", 3)),
        evidence_min_snippet_chars=max(1, _env_int("EVIDENCE_MIN_SNIPPET_CHARS", 20)),
        worker_suggestions_max_chars=max(500, _env_int("WORKER_SUGGESTIONS_MAX_CHARS", 12000)),
        writeback_execute_enabled=_env_bool("WRITEBACK_EXECUTE_ENABLED", False),
    )

