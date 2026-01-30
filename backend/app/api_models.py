from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, ConfigDict


class StatusEntry(BaseModel):
    status: str
    detail: Optional[str] = None


class StatusResponse(BaseModel):
    web: StatusEntry
    worker: StatusEntry
    ollama: StatusEntry
    paperless_base_url: Optional[str] = None
    latency_ms: Optional[int] = None


class QueueStatusResponse(BaseModel):
    enabled: bool
    length: Optional[int] = None
    total: Optional[int] = None
    in_progress: Optional[int] = None
    done: Optional[int] = None
    paused: Optional[bool] = None


class QueueEnqueueResponse(BaseModel):
    enabled: bool
    enqueued: Optional[int] = None


class QueuePeekItem(BaseModel):
    doc_id: Optional[int] = None
    task: Optional[str] = None
    raw: Optional[str] = None


class QueuePeekResponse(BaseModel):
    enabled: bool
    items: list[QueuePeekItem] = []


class QueueCancelResponse(BaseModel):
    enabled: bool
    cancelled: Optional[bool] = None


class QueueResetResponse(BaseModel):
    enabled: bool


class QueuePauseResponse(BaseModel):
    enabled: bool
    paused: bool


class QueueMoveResponse(BaseModel):
    enabled: bool
    moved: bool


class QueueRemoveResponse(BaseModel):
    enabled: bool
    removed: bool


class ConnectionStatus(BaseModel):
    service: str
    status: str
    detail: str
    latency_ms: int


class PaperlessDocument(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: Optional[int] = None
    title: Optional[str] = None
    content: Optional[str] = None
    correspondent: Optional[int] = None
    document_type: Optional[int] = None
    document_date: Optional[str] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    tags: list[int] = []


class DocumentSummary(PaperlessDocument):
    correspondent_name: Optional[str] = None
    has_embeddings: Optional[bool] = None
    has_suggestions: Optional[bool] = None
    has_vision_pages: Optional[bool] = None


class DocumentNoteOut(BaseModel):
    note: Optional[str] = None


class DocumentLocalResponse(BaseModel):
    id: Optional[int] = None
    title: Optional[str] = None
    content: Optional[str] = None
    document_date: Optional[str] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    correspondent: Optional[int] = None
    correspondent_name: Optional[str] = None
    document_type: Optional[int] = None
    document_type_name: Optional[str] = None
    tags: list[int] = []
    notes: list[DocumentNoteOut] = []
    original_file_name: Optional[str] = None
    status: Optional[str] = None


class DocumentsPageResponse(BaseModel):
    count: Optional[int] = None
    next: Optional[str] = None
    previous: Optional[str] = None
    results: list[DocumentSummary] = []


class TagResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: Optional[int] = None
    name: Optional[str] = None
    color: Optional[str] = None
    is_inbox_tag: Optional[bool] = None
    slug: Optional[str] = None
    matching_algorithm: Optional[Any] = None
    is_insensitive: Optional[bool] = None


class CorrespondentResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: Optional[int] = None
    name: Optional[str] = None
    slug: Optional[str] = None
    matching_algorithm: Optional[Any] = None
    is_insensitive: Optional[bool] = None


class DocumentTypeResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: Optional[int] = None
    name: Optional[str] = None
    slug: Optional[str] = None
    matching_algorithm: Optional[Any] = None
    is_insensitive: Optional[bool] = None


class TagsPageResponse(BaseModel):
    count: Optional[int] = None
    next: Optional[str] = None
    previous: Optional[str] = None
    results: list[TagResponse] = []


class CorrespondentsPageResponse(BaseModel):
    count: Optional[int] = None
    next: Optional[str] = None
    previous: Optional[str] = None
    results: list[CorrespondentResponse] = []


class DocumentStatsResponse(BaseModel):
    total: int
    processed: int
    unprocessed: int
    embeddings: int
    vision: int
    suggestions: int
    fully_processed: int


class TextQualityMetrics(BaseModel):
    score: float
    reasons: list[str] = []
    metrics: dict[str, float] = {}


class DocumentTextQualityResponse(BaseModel):
    doc_id: int
    quality: TextQualityMetrics


class SuggestionPayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    raw: Optional[str] = None
    parsed: Optional[dict[str, Any]] = None


class SuggestionsResponse(BaseModel):
    doc_id: int
    suggestions: dict[str, Any] = {}
    queued: Optional[bool] = None


class SuggestFieldVariantsResponse(BaseModel):
    doc_id: int
    source: str
    field: str
    variants: list[Any] = []
    queued: Optional[bool] = None


class ApplyFieldSuggestionResponse(BaseModel):
    status: str
    suggestions: Optional[dict[str, Any]] = None


class ApplySuggestionResponse(BaseModel):
    status: str
    updated: Optional[bool] = None
    unmatched: Optional[Any] = None


class PageTextQuality(BaseModel):
    score: float
    reasons: list[str] = []
    metrics: dict[str, float] = {}


class PageTextOut(BaseModel):
    page: int
    source: str
    text: Optional[str] = None
    quality: Optional[PageTextQuality] = None


class PageTextsResponse(BaseModel):
    doc_id: int
    pages: list[PageTextOut] = []


class EmbeddingIngestResponse(BaseModel):
    ingested: Optional[int] = None
    documents_embedded: Optional[int] = None
    queued: Optional[int] = None
    status: Optional[str] = None


class EmbeddingMatchDocument(BaseModel):
    id: int
    title: Optional[str] = None
    document_date: Optional[str] = None
    created: Optional[str] = None
    correspondent_id: Optional[int] = None
    correspondent_name: Optional[str] = None


class EmbeddingMatch(BaseModel):
    doc_id: Optional[int] = None
    page: Optional[int] = None
    snippet: Optional[str] = None
    score: Optional[float] = None
    source: Optional[str] = None
    quality_score: Optional[float] = None
    bbox: Optional[Any] = None
    document: Optional[EmbeddingMatchDocument] = None


class EmbeddingSearchResponse(BaseModel):
    query: str
    top_k: int
    matches: list[EmbeddingMatch] = []


class EmbeddingStatusResponse(BaseModel):
    status: str
    processed: int
    total: int
    started_at: Optional[str] = None
    last_synced_at: Optional[str] = None
    cancel_requested: Optional[bool] = None
    eta_seconds: Optional[int] = None


class SyncDocumentsResponse(BaseModel):
    count: int
    upserted: int
    incremental: bool
    embedded: int
    status: Optional[str] = None
    queued: Optional[int] = None


class SyncStatusResponse(BaseModel):
    last_synced_at: Optional[str] = None
    status: str
    processed: int
    total: int
    started_at: Optional[str] = None
    cancel_requested: Optional[bool] = None
    eta_seconds: Optional[int] = None


class SyncCancelResponse(BaseModel):
    status: str


class SyncDocumentResponse(BaseModel):
    id: int
    status: str
    embedded: int


class SyncSimpleResponse(BaseModel):
    count: int
    upserted: int


class ChatCitation(BaseModel):
    id: int
    doc_id: Optional[int] = None
    page: Optional[int] = None
    source: Optional[str] = None
    bbox: Optional[Any] = None
    score: Optional[float] = None
    quality_score: Optional[float] = None
    snippet: Optional[str] = None


class ChatResponse(BaseModel):
    question: str
    answer: str
    citations: list[ChatCitation] = []


class ChatHistoryItem(BaseModel):
    question: str
    answer: str


class ChatRequest(BaseModel):
    question: str
    top_k: int = 6
    source: Optional[str] = None
    min_quality: Optional[int] = None
    history: Optional[list[ChatHistoryItem]] = None
