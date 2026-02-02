import { unwrap } from '../api/orval';
import { request } from './http';
import {
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
  getDocumentSuggestionsDocumentsDocIdSuggestionsGet,
  suggestFieldVariantsDocumentsDocIdSuggestionsFieldPost,
  getFieldVariantsDocumentsDocIdSuggestionsFieldVariantsGet,
  applyFieldSuggestionDocumentsDocIdSuggestionsFieldApplyPost,
  applySuggestionToDocumentDocumentsDocIdApplySuggestionPost,
  ingestEmbeddingsEmbeddingsIngestPost,
  ingestDocumentsEmbeddingsIngestDocsPost,
  cancelEmbeddingsEmbeddingsCancelPost,
} from '../api/generated/client';
import type {
  ApplyFieldSuggestionResponse,
  ApplySuggestionResponse,
  ApplySuggestionToDocument,
  CorrespondentResponse,
  CorrespondentsPageResponse,
  DocumentLocalResponse,
  DocumentStatsResponse,
  DocumentSummary,
  DocumentTextQualityResponse,
  DocumentTypeResponse,
  DocumentsPageResponse,
  EmbeddingIngestResponse,
  EmbeddingStatusResponse,
  GetDocumentPageTextsDocumentsDocIdPageTextsGetParams,
  GetDocumentSuggestionsDocumentsDocIdSuggestionsGetParams,
  GetDocumentTextQualityDocumentsDocIdTextQualityGetParams,
  GetFieldVariantsDocumentsDocIdSuggestionsFieldVariantsGetParams,
  IngestDocumentsEmbeddingsIngestDocsPostParams,
  IngestEmbeddingsEmbeddingsIngestPostParams,
  ListDocumentsDocumentsGetParams,
  PageTextOut,
  PageTextsResponse,
  SuggestFieldVariantsResponse,
  SuggestFieldVariantsDocumentsDocIdSuggestionsFieldPostParams,
  SuggestionFieldApply,
  SuggestionFieldRequest,
  SuggestionsResponse,
  SuggestionsResponseSuggestions,
  SyncCancelResponse,
  SyncDocumentResponse,
  SyncDocumentsResponse,
  SyncDocumentsSyncDocumentsPostParams,
  SyncDocumentSyncDocumentsDocIdPostParams,
  SyncStatusResponse,
  TagResponse,
  TagsPageResponse,
} from '../api/generated/model';

export type DocumentRow = DocumentSummary;
export type DocumentDetail = DocumentLocalResponse;
export type Tag = TagResponse;
export type Correspondent = CorrespondentResponse;
export type DocumentType = DocumentTypeResponse;
export type SyncStatus = SyncStatusResponse;
export type EmbedStatus = EmbeddingStatusResponse;
export type DocumentStats = DocumentStatsResponse;
export type PageText = PageTextOut;
export type SuggestionPayload = SuggestionsResponseSuggestions;
export type ProcessMissingResponse = { enabled: boolean; docs: number; enqueued: number; tasks: number };
export type ProcessMissingParams = {
  dry_run?: boolean;
  include_vision_ocr?: boolean;
  include_embeddings?: boolean;
  include_suggestions_paperless?: boolean;
  include_suggestions_vision?: boolean;
  embeddings_mode?: 'auto' | 'paperless' | 'vision';
};
export type ResetIntelligenceResponse = { cleared_embeddings: number; cleared_page_texts: number; cleared_suggestions: number };
export type ClearIntelligenceResponse = {
  cleared_embeddings: number;
  cleared_page_texts: number;
  cleared_suggestions: number;
  qdrant_deleted: number;
  qdrant_errors: number;
};
export type DeleteEmbeddingsResponse = { deleted: number; qdrant_deleted: number; qdrant_errors: number };
export type DeleteSuggestionsResponse = { deleted: number };
export type DeleteVisionOcrResponse = { deleted: number };

export const listDocuments = (params: ListDocumentsDocumentsGetParams) =>
  unwrap<DocumentsPageResponse>(listDocumentsDocumentsGet(params));

export const getDocumentLocal = (id: number) =>
  unwrap<DocumentDetail>(getLocalDocumentDocumentsDocIdLocalGet(id));

export const syncDocuments = (params: SyncDocumentsSyncDocumentsPostParams) =>
  unwrap<SyncDocumentsResponse>(syncDocumentsSyncDocumentsPost(params));

export const syncDocument = (id: number, params: SyncDocumentSyncDocumentsDocIdPostParams) =>
  unwrap<SyncDocumentResponse>(syncDocumentSyncDocumentsDocIdPost(id, params));

export const cancelSync = () => unwrap<SyncCancelResponse>(cancelSyncSyncDocumentsCancelPost());

export const cancelEmbeddings = () => unwrap<SyncCancelResponse>(cancelEmbeddingsEmbeddingsCancelPost());

export const getSyncStatus = () => unwrap<SyncStatus>(syncStatusSyncDocumentsGet());

export const getEmbedStatus = () => unwrap<EmbedStatus>(embeddingStatusEmbeddingsStatusGet());

export const getStats = () => unwrap<DocumentStats>(getDocumentStatsDocumentsStatsGet());

export const getTags = (page = 1, page_size = 200) =>
  unwrap<TagsPageResponse>(listTagsTagsGet({ page, page_size }));

export const getCorrespondents = (page = 1, page_size = 200) =>
  unwrap<CorrespondentsPageResponse>(listCorrespondentsCorrespondentsGet({ page, page_size }));

export const getDocumentType = (id: number) =>
  unwrap<DocumentType>(getDocumentTypeDocumentTypesDocTypeIdGet(id));

export const getPageTexts = (id: number, priority = false) =>
  unwrap<PageTextsResponse>(
    getDocumentPageTextsDocumentsDocIdPageTextsGet(id, { priority } as GetDocumentPageTextsDocumentsDocIdPageTextsGetParams)
  );

export const getTextQuality = (id: number, priority = false) =>
  unwrap<DocumentTextQualityResponse>(
    getDocumentTextQualityDocumentsDocIdTextQualityGet(id, { priority } as GetDocumentTextQualityDocumentsDocIdTextQualityGetParams)
  );

export const getSuggestions = (id: number, params?: GetDocumentSuggestionsDocumentsDocIdSuggestionsGetParams) =>
  unwrap<SuggestionsResponse>(getDocumentSuggestionsDocumentsDocIdSuggestionsGet(id, params));

export const suggestFieldVariants = (
  id: number,
  payload: SuggestionFieldRequest,
  priority = true
) =>
  unwrap<SuggestFieldVariantsResponse>(
    suggestFieldVariantsDocumentsDocIdSuggestionsFieldPost(
      id,
      payload,
      { priority } as SuggestFieldVariantsDocumentsDocIdSuggestionsFieldPostParams
    )
  );

export const fetchFieldVariants = (id: number, source: string, field: string) =>
  unwrap<SuggestFieldVariantsResponse>(
    getFieldVariantsDocumentsDocIdSuggestionsFieldVariantsGet(
      id,
      { source, field } as GetFieldVariantsDocumentsDocIdSuggestionsFieldVariantsGetParams
    )
  );

export const applyFieldSuggestion = (id: number, payload: SuggestionFieldApply) =>
  unwrap<ApplyFieldSuggestionResponse>(applyFieldSuggestionDocumentsDocIdSuggestionsFieldApplyPost(id, payload));

export const applySuggestionToDocument = (id: number, payload: ApplySuggestionToDocument) =>
  unwrap<ApplySuggestionResponse>(applySuggestionToDocumentDocumentsDocIdApplySuggestionPost(id, payload));

export const ingestEmbeddings = (params: IngestEmbeddingsEmbeddingsIngestPostParams) =>
  unwrap<EmbeddingIngestResponse>(ingestEmbeddingsEmbeddingsIngestPost(params));

export const ingestEmbeddingsForDocs = (ids: number[], params: IngestDocumentsEmbeddingsIngestDocsPostParams) =>
  unwrap<EmbeddingIngestResponse>(ingestDocumentsEmbeddingsIngestDocsPost(ids, params));

export const processMissing = (params?: ProcessMissingParams) =>
  request<ProcessMissingResponse>('/documents/process-missing', { method: 'POST', params });

export const resetIntelligence = () =>
  request<ResetIntelligenceResponse>('/documents/reset-intelligence', { method: 'POST' });

export const clearIntelligence = () =>
  request<ClearIntelligenceResponse>('/documents/clear-intelligence', { method: 'POST' });

export const deleteVisionOcr = () =>
  request<DeleteVisionOcrResponse>('/documents/delete-vision-ocr', { method: 'POST' });

export const deleteSuggestions = () =>
  request<DeleteSuggestionsResponse>('/documents/delete-suggestions', { method: 'POST' });

export const deleteEmbeddings = () =>
  request<DeleteEmbeddingsResponse>('/documents/delete-embeddings', { method: 'POST' });
