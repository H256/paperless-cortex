import { unwrap } from '../api/orval'
import {
  cleanupTextsDocumentsCleanupTextsPost,
  enqueueDocumentTaskDocumentsDocIdOperationsEnqueueTaskPost,
  listDocumentsDocumentsGet,
  getDocumentStatsDocumentsStatsGet,
  getLocalDocumentDocumentsDocIdLocalGet,
  syncDocumentsSyncDocumentsPost,
  syncDocumentSyncDocumentsDocIdPost,
  cancelSyncSyncDocumentsCancelPost,
  embeddingStatusEmbeddingsStatusGet,
  syncStatusSyncDocumentsGet,
  listTagsTagsGet,
  listCorrespondentsCorrespondentsGet,
  getDocumentTypeDocumentTypesDocTypeIdGet,
  getDocumentPageTextsDocumentsDocIdPageTextsGet,
  getDocumentTextQualityDocumentsDocIdTextQualityGet,
  getDocumentOcrScoresDocumentsDocIdOcrScoresGet,
  getDocumentSuggestionsDocumentsDocIdSuggestionsGet,
  suggestFieldVariantsDocumentsDocIdSuggestionsFieldPost,
  getFieldVariantsDocumentsDocIdSuggestionsFieldVariantsGet,
  applyFieldSuggestionDocumentsDocIdSuggestionsFieldApplyPost,
  applySuggestionToDocumentDocumentsDocIdApplySuggestionPost,
  cancelEmbeddingsEmbeddingsCancelPost,
  processMissingDocumentsProcessMissingPost,
  resetIntelligenceDocumentsResetIntelligencePost,
  clearIntelligenceDocumentsClearIntelligencePost,
  deleteVisionOcrDocumentsDeleteVisionOcrPost,
  deleteSuggestionsDocumentsDeleteSuggestionsPost,
  deleteEmbeddingsDocumentsDeleteEmbeddingsPost,
  getDashboardDocumentsDashboardGet,
  syncTagsSyncTagsPost,
  syncCorrespondentsSyncCorrespondentsPost,
  getDocumentPipelineFanoutDocumentsDocIdPipelineFanoutGet,
  getDocumentPipelineStatusDocumentsDocIdPipelineStatusGet,
  continueDocumentPipelineDocumentsDocIdPipelineContinuePost,
  resetAndReprocessDocumentDocumentsDocIdOperationsResetAndReprocessPost,
  markDocumentReviewedDocumentsDocIdReviewMarkPost,
} from '../api/generated/client'
import type {
  ApplyFieldSuggestionResponse,
  ApplySuggestionResponse,
  ApplySuggestionToDocument,
  CorrespondentResponse,
  CorrespondentsPageResponse,
  DocumentLocalResponse,
  DocumentStatsResponse,
  DocumentDashboardResponse,
  DocumentSummary,
  DocumentTextQualityResponse,
  DocumentOcrScoresResponse,
  DocumentTypeResponse,
  DocumentsPageResponse,
  EmbeddingStatusResponse,
  GetDocumentPageTextsDocumentsDocIdPageTextsGetParams,
  GetDocumentSuggestionsDocumentsDocIdSuggestionsGetParams,
  GetDocumentTextQualityDocumentsDocIdTextQualityGetParams,
  GetDocumentOcrScoresDocumentsDocIdOcrScoresGetParams,
  GetFieldVariantsDocumentsDocIdSuggestionsFieldVariantsGetParams,
  ListDocumentsDocumentsGetParams,
  PageTextOut,
  PageTextsResponse,
  SuggestFieldVariantsResponse,
  SuggestFieldVariantsDocumentsDocIdSuggestionsFieldPostParams,
  SuggestionFieldApply,
  SuggestionFieldRequest,
  SuggestionsResponse,
  ProcessMissingResponse,
  ProcessMissingDocumentsProcessMissingPostParams,
  ResetIntelligenceResponse,
  ClearIntelligenceResponse,
  DeleteVisionOcrResponse,
  DeleteSuggestionsResponse,
  DeleteEmbeddingsResponse,
  SyncCancelResponse,
  SyncDocumentResponse,
  SyncDocumentsResponse,
  SyncDocumentsSyncDocumentsPostParams,
  SyncDocumentSyncDocumentsDocIdPostParams,
  SyncStatusResponse,
  TagResponse,
  TagsPageResponse,
  SyncSimpleResponse,
  DocumentPipelineFanoutResponse,
  GetDocumentPipelineFanoutDocumentsDocIdPipelineFanoutGetParams,
  CleanupTextsRequest,
  CleanupTextsResponse,
  DocumentTaskRequest,
  DocumentOperationEnqueueResponse,
  DocumentResetReprocessResponse,
  DocumentPipelineStatusResponse,
  DocumentPipelineContinueResponse,
  ContinueDocumentPipelineDocumentsDocIdPipelineContinuePostParams,
  DocumentMarkReviewedResponse,
} from '@/api/generated/model'

export type DocumentRow = DocumentSummary
export type DocumentDetail = DocumentLocalResponse
export type MarkReviewedResult = DocumentMarkReviewedResponse
export type Tag = TagResponse
export type Correspondent = CorrespondentResponse
export type DocumentType = DocumentTypeResponse
export type SyncStatus = SyncStatusResponse
export type EmbedStatus = EmbeddingStatusResponse
export type DocumentStats = DocumentStatsResponse
export type DocumentDashboard = DocumentDashboardResponse
export type PageText = PageTextOut
export type ProcessMissingParams = ProcessMissingDocumentsProcessMissingPostParams
export type VisionProgress = {
  expected_pages?: number | null
  done_pages: number
  missing_pages?: number | null
  max_page?: number | null
  is_complete: boolean
  coverage_percent?: number | null
}
export type PageTextsWithProgress = PageTextsResponse & {
  vision_progress?: VisionProgress | null
}

export const listDocuments = (params: ListDocumentsDocumentsGetParams) =>
  unwrap<DocumentsPageResponse>(listDocumentsDocumentsGet(params))

export const getDocumentLocal = (id: number) =>
  unwrap<DocumentDetail>(getLocalDocumentDocumentsDocIdLocalGet(id))

export const syncDocuments = (params: SyncDocumentsSyncDocumentsPostParams) =>
  unwrap<SyncDocumentsResponse>(syncDocumentsSyncDocumentsPost(params))

export const syncDocument = (id: number, params: SyncDocumentSyncDocumentsDocIdPostParams) =>
  unwrap<SyncDocumentResponse>(syncDocumentSyncDocumentsDocIdPost(id, params))

export const cancelSync = () => unwrap<SyncCancelResponse>(cancelSyncSyncDocumentsCancelPost())

export const cancelEmbeddings = () =>
  unwrap<SyncCancelResponse>(cancelEmbeddingsEmbeddingsCancelPost())

export const getSyncStatus = () => unwrap<SyncStatus>(syncStatusSyncDocumentsGet())

export const getEmbedStatus = () => unwrap<EmbedStatus>(embeddingStatusEmbeddingsStatusGet())

export const getStats = () => unwrap<DocumentStats>(getDocumentStatsDocumentsStatsGet())

export const getDashboard = () => unwrap<DocumentDashboard>(getDashboardDocumentsDashboardGet())

export const getTags = (page = 1, page_size = 200) =>
  unwrap<TagsPageResponse>(listTagsTagsGet({ page, page_size }))

export const getCorrespondents = (page = 1, page_size = 200) =>
  unwrap<CorrespondentsPageResponse>(listCorrespondentsCorrespondentsGet({ page, page_size }))

export const getDocumentType = (id: number) =>
  unwrap<DocumentType>(getDocumentTypeDocumentTypesDocTypeIdGet(id))

export const getPageTexts = (id: number, priority = false) =>
  unwrap<PageTextsWithProgress>(
    getDocumentPageTextsDocumentsDocIdPageTextsGet(id, {
      priority,
    } as GetDocumentPageTextsDocumentsDocIdPageTextsGetParams),
  )

export const getTextQuality = (id: number, priority = false) =>
  unwrap<DocumentTextQualityResponse>(
    getDocumentTextQualityDocumentsDocIdTextQualityGet(id, {
      priority,
    } as GetDocumentTextQualityDocumentsDocIdTextQualityGetParams),
  )

export const getOcrScores = (
  id: number,
  params?: GetDocumentOcrScoresDocumentsDocIdOcrScoresGetParams,
) => unwrap<DocumentOcrScoresResponse>(getDocumentOcrScoresDocumentsDocIdOcrScoresGet(id, params))

export const getSuggestions = (
  id: number,
  params?: GetDocumentSuggestionsDocumentsDocIdSuggestionsGetParams,
) => unwrap<SuggestionsResponse>(getDocumentSuggestionsDocumentsDocIdSuggestionsGet(id, params))

export const suggestFieldVariants = (
  id: number,
  payload: SuggestionFieldRequest,
  priority = true,
) =>
  unwrap<SuggestFieldVariantsResponse>(
    suggestFieldVariantsDocumentsDocIdSuggestionsFieldPost(id, payload, {
      priority,
    } as SuggestFieldVariantsDocumentsDocIdSuggestionsFieldPostParams),
  )

export const fetchFieldVariants = (id: number, source: string, field: string) =>
  unwrap<SuggestFieldVariantsResponse>(
    getFieldVariantsDocumentsDocIdSuggestionsFieldVariantsGet(id, {
      source,
      field,
    } as GetFieldVariantsDocumentsDocIdSuggestionsFieldVariantsGetParams),
  )

export const applyFieldSuggestion = (id: number, payload: SuggestionFieldApply) =>
  unwrap<ApplyFieldSuggestionResponse>(
    applyFieldSuggestionDocumentsDocIdSuggestionsFieldApplyPost(id, payload),
  )

export const applySuggestionToDocument = (id: number, payload: ApplySuggestionToDocument) =>
  unwrap<ApplySuggestionResponse>(
    applySuggestionToDocumentDocumentsDocIdApplySuggestionPost(id, payload),
  )

export const markDocumentReviewed = async (id: number): Promise<MarkReviewedResult> => {
  return unwrap<MarkReviewedResult>(markDocumentReviewedDocumentsDocIdReviewMarkPost(id))
}
export const processMissing = (params?: ProcessMissingParams) =>
  unwrap<ProcessMissingResponse>(processMissingDocumentsProcessMissingPost(params))

export const resetIntelligence = () =>
  unwrap<ResetIntelligenceResponse>(resetIntelligenceDocumentsResetIntelligencePost())

export const clearIntelligence = () =>
  unwrap<ClearIntelligenceResponse>(clearIntelligenceDocumentsClearIntelligencePost())

export const deleteVisionOcr = () =>
  unwrap<DeleteVisionOcrResponse>(deleteVisionOcrDocumentsDeleteVisionOcrPost())

export const deleteSuggestions = () =>
  unwrap<DeleteSuggestionsResponse>(deleteSuggestionsDocumentsDeleteSuggestionsPost())

export const deleteEmbeddings = () =>
  unwrap<DeleteEmbeddingsResponse>(deleteEmbeddingsDocumentsDeleteEmbeddingsPost())

export const syncTags = () => unwrap<SyncSimpleResponse>(syncTagsSyncTagsPost())

export const syncCorrespondents = () =>
  unwrap<SyncSimpleResponse>(syncCorrespondentsSyncCorrespondentsPost())

export type CleanupTextsPayload = CleanupTextsRequest
export type CleanupTextsResult = {
  queued: boolean
  docs: number
  enqueued: number
  processed: number
  updated: number
}
export type DocumentOperationTaskType =
  | 'sync'
  | 'vision_ocr'
  | 'cleanup_texts'
  | 'embeddings_paperless'
  | 'embeddings_vision'
  | 'similarity_index'
  | 'page_notes_paperless'
  | 'page_notes_vision'
  | 'summary_hierarchical'
  | 'suggestions_paperless'
  | 'suggestions_vision'
export type DocumentOperationTaskPayload = Omit<DocumentTaskRequest, 'task'> & {
  task: DocumentOperationTaskType
}
export type DocumentOperationTaskResult = DocumentOperationEnqueueResponse
export type DocumentResetReprocessResult = DocumentResetReprocessResponse
export type DeleteSimilarityIndexResult = {
  deleted: number
  qdrant_deleted: number
  qdrant_errors: number
}
export type MissingVectorChunkItem = {
  doc_id: number
  title?: string | null
  embedding_source?: string | null
  chunk_count: number
  expected_vectors: number
  found_vectors: number
  fully_missing: boolean
  embedded_at?: string | null
}
export type MissingVectorChunkAuditResult = {
  provider: string
  scanned_docs: number
  affected_docs: number
  fully_missing_docs: number
  partial_missing_docs: number
  limit: number
  truncated: boolean
  items: MissingVectorChunkItem[]
}

export type DocumentPipelineStepStatus = {
  key: string
  required: boolean
  done: boolean
  detail?: string | null
}

export type DocumentPipelineStatus = DocumentPipelineStatusResponse

export type ContinuePipelinePayload = ContinueDocumentPipelineDocumentsDocIdPipelineContinuePostParams
export type ContinuePipelineResult = DocumentPipelineContinueResponse

export type DocumentPipelineFanout = DocumentPipelineFanoutResponse
export type PipelineFanoutParams = GetDocumentPipelineFanoutDocumentsDocIdPipelineFanoutGetParams

export const cleanupTexts = (payload: CleanupTextsPayload) =>
  unwrap<CleanupTextsResponse>(cleanupTextsDocumentsCleanupTextsPost(payload)).then((result) => ({
    queued: Boolean(result.queued),
    docs: Number(result.docs ?? 0),
    enqueued: Number(result.enqueued ?? 0),
    processed: Number(result.processed ?? 0),
    updated: Number(result.updated ?? 0),
  }))

export const enqueueDocumentTask = (id: number, payload: DocumentOperationTaskPayload) =>
  unwrap<DocumentOperationTaskResult>(enqueueDocumentTaskDocumentsDocIdOperationsEnqueueTaskPost(id, payload))

export const resetAndReprocessDocument = (id: number, enqueue = true) =>
  unwrap<DocumentResetReprocessResult>(resetAndReprocessDocumentDocumentsDocIdOperationsResetAndReprocessPost(id, { enqueue }))

export const getDocumentPipelineStatus = (id: number) =>
  unwrap<DocumentPipelineStatus>(getDocumentPipelineStatusDocumentsDocIdPipelineStatusGet(id))

export const getDocumentPipelineFanout = (id: number, params?: PipelineFanoutParams) =>
  unwrap<DocumentPipelineFanout>(getDocumentPipelineFanoutDocumentsDocIdPipelineFanoutGet(id, params))

export const continueDocumentPipeline = (id: number, payload: ContinuePipelinePayload = {}) =>
  unwrap<ContinuePipelineResult>(continueDocumentPipelineDocumentsDocIdPipelineContinuePost(id, payload))

export const deleteSimilarityIndex = async (docId?: number): Promise<DeleteSimilarityIndexResult> => {
  const params = typeof docId === 'number' ? `?doc_id=${encodeURIComponent(String(docId))}` : ''
  const response = await fetch(`/api/documents/delete/similarity-index${params}`, {
    method: 'POST',
  })
  const body = await response.text()
  const parsed = body ? (JSON.parse(body) as Record<string, unknown>) : {}
  if (!response.ok) {
    const detail = typeof parsed.detail === 'string' ? parsed.detail : `HTTP ${response.status}`
    throw new Error(detail)
  }
  return {
    deleted: Number(parsed.deleted ?? 0),
    qdrant_deleted: Number(parsed.qdrant_deleted ?? 0),
    qdrant_errors: Number(parsed.qdrant_errors ?? 0),
  }
}

export const findMissingVectorChunks = async (limit = 100): Promise<MissingVectorChunkAuditResult> => {
  const response = await fetch(
    `/api/documents/audit/missing-vector-chunks?limit=${encodeURIComponent(String(limit))}`,
  )
  const body = await response.text()
  const parsed = body ? (JSON.parse(body) as Record<string, unknown>) : {}
  if (!response.ok) {
    const detail = typeof parsed.detail === 'string' ? parsed.detail : `HTTP ${response.status}`
    throw new Error(detail)
  }
  const rawItems = Array.isArray(parsed.items) ? parsed.items : []
  const items: MissingVectorChunkItem[] = rawItems
    .filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null)
    .map((item) => ({
      doc_id: Number(item.doc_id ?? 0),
      title: typeof item.title === 'string' ? item.title : null,
      embedding_source: typeof item.embedding_source === 'string' ? item.embedding_source : null,
      chunk_count: Number(item.chunk_count ?? 0),
      expected_vectors: Number(item.expected_vectors ?? 0),
      found_vectors: Number(item.found_vectors ?? 0),
      fully_missing: Boolean(item.fully_missing),
      embedded_at: typeof item.embedded_at === 'string' ? item.embedded_at : null,
    }))
  return {
    provider: typeof parsed.provider === 'string' ? parsed.provider : 'unknown',
    scanned_docs: Number(parsed.scanned_docs ?? 0),
    affected_docs: Number(parsed.affected_docs ?? 0),
    fully_missing_docs: Number(parsed.fully_missing_docs ?? 0),
    partial_missing_docs: Number(parsed.partial_missing_docs ?? 0),
    limit: Number(parsed.limit ?? limit),
    truncated: Boolean(parsed.truncated),
    items,
  }
}
