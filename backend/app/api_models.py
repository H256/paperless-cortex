from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, ConfigDict


class StatusEntry(BaseModel):
    status: str
    detail: Optional[str] = None


class StatusResponse(BaseModel):
    web: StatusEntry
    worker: StatusEntry
    llm: StatusEntry
    llm_text: StatusEntry
    llm_embedding: StatusEntry
    llm_vision: StatusEntry
    paperless_base_url: Optional[str] = None
    llm_base_url: Optional[str] = None
    qdrant_url: Optional[str] = None
    redis_host: Optional[str] = None
    text_model: Optional[str] = None
    embedding_model: Optional[str] = None
    vision_model: Optional[str] = None
    latency_ms: Optional[int] = None


class QueueStatusResponse(BaseModel):
    enabled: bool
    length: Optional[int] = None
    total: Optional[int] = None
    in_progress: Optional[int] = None
    done: Optional[int] = None
    paused: Optional[bool] = None
    last_run_seconds: Optional[float] = None
    last_run_at: Optional[int] = None


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


class QueueWorkerLockStatusResponse(BaseModel):
    enabled: bool
    has_lock: bool
    owner: Optional[str] = None
    ttl_seconds: Optional[int] = None


class QueueWorkerLockResetResponse(BaseModel):
    enabled: bool
    reset: bool
    had_lock: bool
    reason: Optional[str] = None


class QueueRunningResponse(BaseModel):
    enabled: bool
    task: Optional[QueuePeekItem] = None
    started_at: Optional[int] = None


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
    local_cached: Optional[bool] = None
    local_overrides: Optional[bool] = None
    review_status: Optional[str] = None
    reviewed_at: Optional[str] = None
    has_embeddings: Optional[bool] = None
    has_suggestions: Optional[bool] = None
    has_suggestions_paperless: Optional[bool] = None
    has_suggestions_vision: Optional[bool] = None
    has_vision_pages: Optional[bool] = None
    pending_tag_names: list[str] = []


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
    local_overrides: Optional[bool] = None
    sync_status: Optional[str] = None
    review_status: Optional[str] = None
    reviewed_at: Optional[str] = None
    paperless_modified: Optional[str] = None
    pending_tag_names: list[str] = []
    has_embeddings: Optional[bool] = None
    embedding_source: Optional[str] = None
    embedding_chunk_count: Optional[int] = None
    has_embedding_for_preferred_source: Optional[bool] = None
    has_suggestions_paperless: Optional[bool] = None
    has_suggestions_vision: Optional[bool] = None
    has_vision_pages: Optional[bool] = None
    vision_pages_done: Optional[int] = None
    vision_pages_expected: Optional[int] = None
    has_complete_vision_pages: Optional[bool] = None
    has_page_notes_paperless: Optional[bool] = None
    has_page_notes_vision: Optional[bool] = None
    page_notes_paperless_done: Optional[int] = None
    page_notes_vision_done: Optional[int] = None
    page_notes_expected: Optional[int] = None
    has_complete_page_notes_paperless: Optional[bool] = None
    has_complete_page_notes_vision: Optional[bool] = None
    has_hierarchical_summary: Optional[bool] = None
    is_large_document: Optional[bool] = None
    preferred_processing_source: Optional[str] = None


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


class DashboardCount(BaseModel):
    id: Optional[int] = None
    name: str
    count: int


class PageCountBucket(BaseModel):
    label: str
    count: int


class MonthlyProcessingBucket(BaseModel):
    label: str
    total: int
    processed: int
    unprocessed: int


class DocumentDashboardResponse(BaseModel):
    stats: DocumentStatsResponse
    correspondents: list[DashboardCount] = []
    top_correspondents: list[DashboardCount] = []
    tags: list[DashboardCount] = []
    top_tags: list[DashboardCount] = []
    page_counts: list[PageCountBucket] = []
    document_types: list[DashboardCount] = []
    unprocessed_by_correspondent: list[DashboardCount] = []
    monthly_processing: list[MonthlyProcessingBucket] = []


class TextQualityMetrics(BaseModel):
    score: float
    reasons: list[str] = []
    metrics: dict[str, float] = {}


class DocumentTextQualityResponse(BaseModel):
    doc_id: int
    quality: TextQualityMetrics


class DocumentOcrScoreOut(BaseModel):
    source: str
    verdict: Optional[str] = None
    quality_score: Optional[float] = None
    components: dict[str, float] = {}
    noise: dict[str, float] = {}
    ppl: dict[str, Any] = {}
    model_name: Optional[str] = None
    processed_at: Optional[str] = None


class DocumentOcrScoresResponse(BaseModel):
    doc_id: int
    scores: list[DocumentOcrScoreOut] = []


class SuggestionPayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    raw: Optional[str] = None
    parsed: Optional[dict[str, Any]] = None


class SuggestionsResponse(BaseModel):
    doc_id: int
    suggestions: dict[str, Any] = {}
    suggestions_meta: Optional[dict[str, Any]] = None
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
    vision_progress: Optional[dict[str, Any]] = None


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
    combined_score: Optional[float] = None
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
    marked_deleted: Optional[int] = None


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


class ProcessMissingResponse(BaseModel):
    enabled: bool
    docs: int
    enqueued: int
    tasks: int
    dry_run: bool = False
    selected: Optional[int] = None
    missing_docs: Optional[int] = None
    missing_vision_ocr: Optional[int] = None
    missing_embeddings: Optional[int] = None
    missing_embeddings_paperless: Optional[int] = None
    missing_embeddings_vision: Optional[int] = None
    missing_page_notes: Optional[int] = None
    missing_summary_hierarchical: Optional[int] = None
    missing_suggestions_paperless: Optional[int] = None
    missing_suggestions_vision: Optional[int] = None


class PipelineStepStatus(BaseModel):
    key: str
    required: bool
    done: bool
    detail: Optional[str] = None


class DocumentPipelineStatusResponse(BaseModel):
    doc_id: int
    preferred_source: str
    is_large_document: bool
    sync_ok: bool
    paperless_ok: bool
    vision_ok: bool
    large_ok: bool
    steps: list[PipelineStepStatus] = []
    missing_tasks: list[dict[str, Any]] = []


class DocumentPipelineContinueResponse(BaseModel):
    enabled: bool
    doc_id: int
    dry_run: bool = False
    missing_tasks: int = 0
    enqueued: int = 0


class ResetIntelligenceResponse(BaseModel):
    cleared_embeddings: int
    cleared_page_texts: int
    cleared_suggestions: int


class ClearIntelligenceResponse(BaseModel):
    cleared_documents: int
    cleared_embeddings: int
    cleared_page_texts: int
    cleared_suggestions: int
    qdrant_deleted: int
    qdrant_errors: int


class DeleteEmbeddingsResponse(BaseModel):
    deleted: int
    qdrant_deleted: int
    qdrant_errors: int


class DeleteSuggestionsResponse(BaseModel):
    deleted: int


class DeleteVisionOcrResponse(BaseModel):
    deleted: int


class CleanupTextsResponse(BaseModel):
    queued: bool = False
    docs: int = 0
    enqueued: int = 0
    processed: int = 0
    updated: int = 0


class DocumentOperationEnqueueResponse(BaseModel):
    enabled: bool
    enqueued: int
    task: str
    doc_id: int


class DocumentResetReprocessResponse(BaseModel):
    doc_id: int
    synced: bool
    reset: bool
    enqueued: int


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


class WritebackFieldDiff(BaseModel):
    field: str
    original: Any = None
    proposed: Any = None
    changed: bool


class WritebackDryRunItem(BaseModel):
    doc_id: int
    changed: bool
    changed_fields: list[str] = []
    title: WritebackFieldDiff
    document_date: WritebackFieldDiff
    correspondent: WritebackFieldDiff
    tags: WritebackFieldDiff
    note: WritebackFieldDiff


class WritebackDryRunPreviewResponse(BaseModel):
    count: int
    page: int
    page_size: int
    items: list[WritebackDryRunItem] = []


class WritebackDryRunExecuteRequest(BaseModel):
    doc_ids: list[int]


class WritebackDryRunCall(BaseModel):
    doc_id: int
    method: str
    path: str
    payload: dict[str, Any] = {}


class WritebackDryRunExecuteResponse(BaseModel):
    docs_selected: int
    docs_changed: int
    calls: list[WritebackDryRunCall] = []


class WritebackExecuteNowRequest(BaseModel):
    doc_ids: list[int]


class WritebackExecuteNowResponse(BaseModel):
    docs_selected: int
    docs_changed: int
    calls_count: int
    doc_ids: list[int] = []
    calls: list[WritebackDryRunCall] = []


class WritebackDirectExecuteRequest(BaseModel):
    known_paperless_modified: Optional[str] = None
    resolutions: dict[str, str] = {}


class WritebackConflictField(BaseModel):
    field: str
    paperless: Any = None
    local: Any = None


class WritebackDirectExecuteResponse(BaseModel):
    status: str
    docs_changed: int
    calls_count: int
    doc_ids: list[int] = []
    calls: list[WritebackDryRunCall] = []
    conflicts: list[WritebackConflictField] = []


class WritebackJobCreateRequest(BaseModel):
    doc_ids: list[int]


class WritebackJobExecuteRequest(BaseModel):
    dry_run: bool = True


class WritebackExecutePendingRequest(BaseModel):
    dry_run: bool = True
    limit: int = 0


class WritebackJobSummary(BaseModel):
    id: int
    status: str
    dry_run: bool
    docs_selected: int
    docs_changed: int
    calls_count: int
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    error: Optional[str] = None


class WritebackJobDetail(WritebackJobSummary):
    doc_ids: list[int] = []
    calls: list[WritebackDryRunCall] = []


class WritebackJobListResponse(BaseModel):
    items: list[WritebackJobSummary] = []


class WritebackHistoryResponse(BaseModel):
    items: list[WritebackJobSummary] = []


class WritebackExecutePendingJobResult(BaseModel):
    job_id: int
    status: str
    dry_run: bool
    docs_selected: int
    docs_changed: int
    calls_count: int
    doc_ids: list[int] = []
    error: Optional[str] = None


class WritebackExecutePendingResponse(BaseModel):
    processed: int
    completed: int
    failed: int
    job_ids: list[int] = []
    doc_ids: list[int] = []
    results: list[WritebackExecutePendingJobResult] = []
