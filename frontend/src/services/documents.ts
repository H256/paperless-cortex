import { unwrap } from '../api/orval';
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
  processMissingDocumentsProcessMissingPost,
  resetIntelligenceDocumentsResetIntelligencePost,
  clearIntelligenceDocumentsClearIntelligencePost,
  deleteVisionOcrDocumentsDeleteVisionOcrPost,
  deleteSuggestionsDocumentsDeleteSuggestionsPost,
  deleteEmbeddingsDocumentsDeleteEmbeddingsPost,
  getDashboardDocumentsDashboardGet,
} from '../api/generated/client';
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
} from '../api/generated/model';

export type DocumentRow = DocumentSummary;
export type DocumentDetail = DocumentLocalResponse;
export type Tag = TagResponse;
export type Correspondent = CorrespondentResponse;
export type DocumentType = DocumentTypeResponse;
export type SyncStatus = SyncStatusResponse;
export type EmbedStatus = EmbeddingStatusResponse;
export type DocumentStats = DocumentStatsResponse;
export type DocumentDashboard = DocumentDashboardResponse;
export type PageText = PageTextOut;
export type SuggestionPayload = SuggestionsResponseSuggestions;
export type ProcessMissingParams = ProcessMissingDocumentsProcessMissingPostParams;

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

export const getDashboard = () => unwrap<DocumentDashboard>(getDashboardDocumentsDashboardGet());

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
  unwrap<ProcessMissingResponse>(processMissingDocumentsProcessMissingPost(params));

export const resetIntelligence = () =>
  unwrap<ResetIntelligenceResponse>(resetIntelligenceDocumentsResetIntelligencePost());

export const clearIntelligence = () =>
  unwrap<ClearIntelligenceResponse>(clearIntelligenceDocumentsClearIntelligencePost());

export const deleteVisionOcr = () =>
  unwrap<DeleteVisionOcrResponse>(deleteVisionOcrDocumentsDeleteVisionOcrPost());

export const deleteSuggestions = () =>
  unwrap<DeleteSuggestionsResponse>(deleteSuggestionsDocumentsDeleteSuggestionsPost());

export const deleteEmbeddings = () =>
  unwrap<DeleteEmbeddingsResponse>(deleteEmbeddingsDocumentsDeleteEmbeddingsPost());
