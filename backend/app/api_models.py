from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DocumentNoteIn(BaseModel):
    id: int
    note: str | None = None
    created: str | None = None
    user: dict[str, Any] | None = None


class DocumentIn(BaseModel):
    id: int
    title: str | None = None
    content: str | None = None
    correspondent: int | None = None
    document_type: int | None = None
    document_date: str | None = None
    created: str | None = None
    modified: str | None = None
    added: str | None = None
    deleted_at: str | None = None
    archive_serial_number: int | None = None
    original_file_name: str | None = None
    mime_type: str | None = None
    page_count: int | None = None
    owner: int | None = None
    user_can_change: bool | None = None
    is_shared_by_requester: bool | None = None
    notes: list[DocumentNoteIn] = Field(default_factory=list)
    tags: list[int] = Field(default_factory=list)


class TagIn(BaseModel):
    id: int
    name: str | None = None
    color: str | None = None
    is_inbox_tag: bool | None = None
    slug: str | None = None
    matching_algorithm: int | str | None = None
    is_insensitive: bool | None = None


class CorrespondentIn(BaseModel):
    id: int
    name: str | None = None
    slug: str | None = None
    matching_algorithm: int | str | None = None
    is_insensitive: bool | None = None


class DocumentTypeIn(BaseModel):
    id: int
    name: str | None = None
    slug: str | None = None
    matching_algorithm: int | str | None = None
    is_insensitive: bool | None = None


class StatusEntry(BaseModel):
    status: str
    detail: str | None = None


class StatusResponse(BaseModel):
    web: StatusEntry
    worker: StatusEntry
    llm: StatusEntry
    llm_text: StatusEntry
    llm_embedding: StatusEntry
    llm_vision: StatusEntry
    paperless_base_url: str | None = None
    llm_base_url: str | None = None
    qdrant_url: str | None = None
    redis_host: str | None = None
    text_model: str | None = None
    chat_model: str | None = None
    embedding_model: str | None = None
    vision_model: str | None = None
    evidence_max_pages: int | None = None
    evidence_min_snippet_chars: int | None = None
    app_version: str | None = None
    api_version: str | None = None
    frontend_version: str | None = None
    latency_ms: int | None = None


class QueueStatusResponse(BaseModel):
    enabled: bool
    length: int | None = None
    total: int | None = None
    in_progress: int | None = None
    done: int | None = None
    paused: bool | None = None
    last_run_seconds: float | None = None
    last_run_at: int | None = None


class QueueEnqueueResponse(BaseModel):
    enabled: bool
    enqueued: int | None = None


class QueuePeekItem(BaseModel):
    doc_id: int | None = None
    task: str | None = None
    raw: str | None = None


class QueuePeekResponse(BaseModel):
    enabled: bool
    items: list[QueuePeekItem] = []


class QueueCancelResponse(BaseModel):
    enabled: bool
    cancelled: bool | None = None


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
    owner: str | None = None
    ttl_seconds: int | None = None


class QueueWorkerLockResetResponse(BaseModel):
    enabled: bool
    reset: bool
    had_lock: bool
    reason: str | None = None


class QueueRunningResponse(BaseModel):
    enabled: bool
    task: QueuePeekItem | None = None
    started_at: int | None = None


class QueueDlqItem(BaseModel):
    task: dict[str, Any] | None = None
    error_type: str | None = None
    error_message: str | None = None
    attempt: int | None = None
    created_at: int | None = None


class QueueDlqResponse(BaseModel):
    enabled: bool
    items: list[QueueDlqItem] = []


class QueueDlqActionResponse(BaseModel):
    enabled: bool
    ok: bool


class QueueDelayedItem(BaseModel):
    task: dict[str, Any] | None = None
    raw: str | None = None
    due_at: int | None = None
    due_in_seconds: int | None = None


class QueueDelayedResponse(BaseModel):
    enabled: bool
    items: list[QueueDelayedItem] = []


class ErrorTypeDetail(BaseModel):
    code: str
    retryable: bool
    category: str
    description: str


class ErrorTypeCatalogResponse(BaseModel):
    enabled: bool
    items: list[ErrorTypeDetail] = []


class TaskRunItem(BaseModel):
    id: int
    doc_id: int | None = None
    task: str
    source: str | None = None
    status: str
    worker_id: str | None = None
    attempt: int
    checkpoint: dict[str, Any] | None = None
    error_type: str | None = None
    error_retryable: bool | None = None
    error_category: str | None = None
    error_message: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: int | None = None
    created_at: str | None = None
    updated_at: str | None = None


class TaskRunListResponse(BaseModel):
    enabled: bool
    count: int
    items: list[TaskRunItem] = []


class ConnectionStatus(BaseModel):
    service: str
    status: str
    detail: str
    latency_ms: int


class PaperlessDocument(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: int | None = None
    title: str | None = None
    content: str | None = None
    correspondent: int | None = None
    document_type: int | None = None
    document_date: str | None = None
    created: str | None = None
    modified: str | None = None
    tags: list[int] = []


class DocumentSummary(PaperlessDocument):
    correspondent_name: str | None = None
    pending_correspondent_name: str | None = None
    local_cached: bool | None = None
    local_overrides: bool | None = None
    review_status: str | None = None
    reviewed_at: str | None = None
    has_embeddings: bool | None = None
    has_suggestions: bool | None = None
    has_suggestions_paperless: bool | None = None
    has_suggestions_vision: bool | None = None
    has_vision_pages: bool | None = None
    pending_tag_names: list[str] = []


class SimilarDocumentMatch(BaseModel):
    doc_id: int
    score: float | None = None
    document: DocumentSummary | None = None


class SimilarDocumentsResponse(BaseModel):
    doc_id: int
    top_k: int
    matches: list[SimilarDocumentMatch] = []


class SimilarMetadata(BaseModel):
    title: str | None = None
    tags: list[str] = []
    correspondent: str | None = None
    documentType: str | None = None
    language: str | None = None


class SimilarMetadataResponse(BaseModel):
    doc_id: int
    top_k: int
    metadata: SimilarMetadata


class DocumentNoteOut(BaseModel):
    note: str | None = None


class DocumentLocalResponse(BaseModel):
    id: int | None = None
    title: str | None = None
    content: str | None = None
    document_date: str | None = None
    created: str | None = None
    modified: str | None = None
    correspondent: int | None = None
    correspondent_name: str | None = None
    document_type: int | None = None
    document_type_name: str | None = None
    tags: list[int] = []
    notes: list[DocumentNoteOut] = []
    original_file_name: str | None = None
    status: str | None = None
    local_overrides: bool | None = None
    sync_status: str | None = None
    review_status: str | None = None
    reviewed_at: str | None = None
    paperless_modified: str | None = None
    pending_tag_names: list[str] = []
    pending_correspondent_name: str | None = None
    has_embeddings: bool | None = None
    embedding_source: str | None = None
    embedding_chunk_count: int | None = None
    has_embedding_for_preferred_source: bool | None = None
    has_suggestions_paperless: bool | None = None
    has_suggestions_vision: bool | None = None
    has_vision_pages: bool | None = None
    vision_pages_done: int | None = None
    vision_pages_expected: int | None = None
    has_complete_vision_pages: bool | None = None
    has_page_notes_paperless: bool | None = None
    has_page_notes_vision: bool | None = None
    page_notes_paperless_done: int | None = None
    page_notes_vision_done: int | None = None
    page_notes_expected: int | None = None
    has_complete_page_notes_paperless: bool | None = None
    has_complete_page_notes_vision: bool | None = None
    has_hierarchical_summary: bool | None = None
    is_large_document: bool | None = None
    preferred_processing_source: str | None = None


class DocumentMarkReviewedResponse(BaseModel):
    status: str
    doc_id: int
    reviewed_at: str | None = None


class DocumentsPageResponse(BaseModel):
    count: int | None = None
    next: str | None = None
    previous: str | None = None
    results: list[DocumentSummary] = []


class TagResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: int | None = None
    name: str | None = None
    color: str | None = None
    is_inbox_tag: bool | None = None
    slug: str | None = None
    matching_algorithm: Any | None = None
    is_insensitive: bool | None = None


class CorrespondentResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: int | None = None
    name: str | None = None
    slug: str | None = None
    matching_algorithm: Any | None = None
    is_insensitive: bool | None = None


class DocumentTypeResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: int | None = None
    name: str | None = None
    slug: str | None = None
    matching_algorithm: Any | None = None
    is_insensitive: bool | None = None


class TagsPageResponse(BaseModel):
    count: int | None = None
    next: str | None = None
    previous: str | None = None
    results: list[TagResponse] = []


class CorrespondentsPageResponse(BaseModel):
    count: int | None = None
    next: str | None = None
    previous: str | None = None
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
    id: int | None = None
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
    verdict: str | None = None
    quality_score: float | None = None
    components: dict[str, float] = {}
    noise: dict[str, float] = {}
    ppl: dict[str, Any] = {}
    model_name: str | None = None
    processed_at: str | None = None


class DocumentOcrScoresResponse(BaseModel):
    doc_id: int
    scores: list[DocumentOcrScoreOut] = []


class SuggestionPayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    raw: str | None = None
    parsed: dict[str, Any] | None = None


class SuggestionsResponse(BaseModel):
    doc_id: int
    suggestions: dict[str, Any] = {}
    suggestions_meta: dict[str, Any] | None = None
    queued: bool | None = None


class SuggestFieldVariantsResponse(BaseModel):
    doc_id: int
    source: str
    field: str
    variants: list[Any] = []
    queued: bool | None = None


class ApplyFieldSuggestionResponse(BaseModel):
    status: str
    suggestions: dict[str, Any] | None = None


class ApplySuggestionResponse(BaseModel):
    status: str
    updated: bool | None = None
    unmatched: Any | None = None


class PageTextQuality(BaseModel):
    score: float
    reasons: list[str] = []
    metrics: dict[str, float] = {}


class PageTextOut(BaseModel):
    page: int
    source: str
    text: str | None = None
    quality: PageTextQuality | None = None


class PageTextsResponse(BaseModel):
    doc_id: int
    pages: list[PageTextOut] = []
    vision_progress: dict[str, Any] | None = None


class EmbeddingIngestResponse(BaseModel):
    ingested: int | None = None
    documents_embedded: int | None = None
    queued: int | None = None
    status: str | None = None


class EmbeddingMatchDocument(BaseModel):
    id: int
    title: str | None = None
    document_date: str | None = None
    created: str | None = None
    correspondent_id: int | None = None
    correspondent_name: str | None = None


class EmbeddingMatch(BaseModel):
    doc_id: int | None = None
    page: int | None = None
    snippet: str | None = None
    score: float | None = None
    combined_score: float | None = None
    source: str | None = None
    quality_score: float | None = None
    bbox: Any | None = None
    document: EmbeddingMatchDocument | None = None


class EmbeddingSearchResponse(BaseModel):
    query: str
    top_k: int
    matches: list[EmbeddingMatch] = []


class EmbeddingStatusResponse(BaseModel):
    status: str
    processed: int
    total: int
    started_at: str | None = None
    last_synced_at: str | None = None
    cancel_requested: bool | None = None
    eta_seconds: int | None = None


class SyncDocumentsResponse(BaseModel):
    count: int
    upserted: int
    incremental: bool
    embedded: int
    status: str | None = None
    queued: int | None = None
    marked_deleted: int | None = None


class SyncStatusResponse(BaseModel):
    last_synced_at: str | None = None
    status: str
    processed: int
    total: int
    started_at: str | None = None
    cancel_requested: bool | None = None
    eta_seconds: int | None = None


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
    selected: int | None = None
    missing_docs: int | None = None
    missing_vision_ocr: int | None = None
    missing_embeddings: int | None = None
    missing_embeddings_paperless: int | None = None
    missing_embeddings_vision: int | None = None
    missing_doc_similarity_index: int | None = None
    missing_page_notes: int | None = None
    missing_summary_hierarchical: int | None = None
    missing_evidence_index: int | None = None
    missing_suggestions_paperless: int | None = None
    missing_suggestions_vision: int | None = None
    missing_by_step: dict[str, int] = {}
    preview_docs: list[dict[str, Any]] = []


class PipelineStepStatus(BaseModel):
    key: str
    required: bool
    done: bool
    detail: str | None = None


class DocumentPipelineStatusResponse(BaseModel):
    doc_id: int
    preferred_source: str
    is_large_document: bool
    sync_ok: bool
    evidence_ok: bool
    paperless_ok: bool
    vision_ok: bool
    large_ok: bool
    steps: list[PipelineStepStatus] = []
    missing_tasks: list[dict[str, Any]] = []


class PipelineFanoutItem(BaseModel):
    order: int
    task: str
    source: str | None = None
    status: str
    detail: str | None = None
    checkpoint: dict[str, Any] | None = None
    error_type: str | None = None
    error_message: str | None = None
    last_started_at: str | None = None
    last_finished_at: str | None = None


class DocumentPipelineFanoutResponse(BaseModel):
    doc_id: int
    enabled: bool
    items: list[PipelineFanoutItem] = []


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


class DeleteSimilarityIndexResponse(BaseModel):
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
    doc_id: int | None = None
    page: int | None = None
    source: str | None = None
    bbox: Any | None = None
    score: float | None = None
    quality_score: float | None = None
    snippet: str | None = None
    evidence_status: str | None = None
    evidence_confidence: float | None = None
    evidence_error: str | None = None


class ChatResponse(BaseModel):
    question: str
    answer: str
    conversation_id: str
    citations: list[ChatCitation] = []


class ChatHistoryItem(BaseModel):
    question: str
    answer: str


class ChatRequest(BaseModel):
    question: str
    top_k: int = 6
    source: str | None = None
    min_quality: int | None = None
    doc_id: int | None = None
    relationship_mode: str | None = None
    history: list[ChatHistoryItem] | None = None
    conversation_id: str | None = None


class ChatFollowupsRequest(BaseModel):
    question: str
    answer: str
    citations: list[ChatCitation] = []
    doc_id: int | None = None
    relationship_mode: str | None = None


class ChatFollowupsResponse(BaseModel):
    questions: list[str] = []


class EvidenceCitationRequest(BaseModel):
    doc_id: int
    page: int
    snippet: str
    source: str | None = None
    bbox: Any | None = None


class EvidenceResolveRequest(BaseModel):
    citations: list[EvidenceCitationRequest] = []
    max_pages: int = 3
    timeout_seconds: int = 45


class EvidenceMatch(BaseModel):
    doc_id: int
    page: int
    snippet: str
    bbox: Any | None = None
    confidence: float = 0.0
    status: str
    error: str | None = None


class EvidenceResolveResponse(BaseModel):
    count: int
    matches: list[EvidenceMatch] = []


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
    known_paperless_modified: str | None = None
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
    created_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None


class WritebackJobDetail(WritebackJobSummary):
    doc_ids: list[int] = []
    calls: list[WritebackDryRunCall] = []


class WritebackJobListResponse(BaseModel):
    items: list[WritebackJobSummary] = []


class WritebackJobDeleteResponse(BaseModel):
    ok: bool
    removed: bool
    job_id: int


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
    error: str | None = None


class WritebackExecutePendingResponse(BaseModel):
    processed: int
    completed: int
    failed: int
    job_ids: list[int] = []
    doc_ids: list[int] = []
    results: list[WritebackExecutePendingJobResult] = []
