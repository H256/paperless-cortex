import { unwrap } from '../api/orval'
import {
  createWritebackJobWritebackJobsPost,
  deleteWritebackJobWritebackJobsJobIdDelete,
  dryRunExecuteWritebackDryRunExecutePost,
  dryRunPreviewWritebackDryRunPreviewGet,
  executePendingWritebackJobsWritebackJobsExecutePendingPost,
  executeWritebackDirectForDocumentWritebackDocumentsDocIdExecuteDirectPost,
  executeWritebackJobWritebackJobsJobIdExecutePost,
  executeWritebackNowWritebackExecuteNowPost,
  getWritebackJobWritebackJobsJobIdGet,
  listWritebackJobsWritebackJobsGet,
  writebackHistoryWritebackHistoryGet,
} from '../api/generated/client'
import type {
  DryRunPreviewWritebackDryRunPreviewGetParams,
  WritebackDirectExecuteRequest,
  WritebackDirectExecuteResponse,
  WritebackDryRunExecuteResponse,
  WritebackDryRunItem as WritebackDryRunItemModel,
  WritebackDryRunPreviewResponse,
  WritebackExecuteNowResponse,
  WritebackExecutePendingResponse,
  WritebackJobDetail,
  WritebackJobListResponse,
  WritebackJobSummary as WritebackJobSummaryModel,
  WritebackConflictField as WritebackConflictFieldModel,
  WritebackJobDeleteResponse,
} from '../api/generated/model'

export type WritebackFieldDiff = WritebackDryRunItemModel['title']
export type WritebackDryRunPreview = WritebackDryRunPreviewResponse
export type WritebackDryRunExecute = WritebackDryRunExecuteResponse
export type WritebackExecuteNow = WritebackExecuteNowResponse
export type WritebackDirectExecute = WritebackDirectExecuteResponse
export type WritebackJob = WritebackJobSummaryModel
export type WritebackJobList = WritebackJobListResponse
export type WritebackExecutePending = WritebackExecutePendingResponse
export type WritebackJobSummary = WritebackJobSummaryModel
export type WritebackDryRunItem = WritebackDryRunItemModel
export type WritebackConflictField = WritebackConflictFieldModel
export type WritebackJobDeleteResult = WritebackJobDeleteResponse

export const getWritebackDryRunPreview = (params: DryRunPreviewWritebackDryRunPreviewGetParams) =>
  unwrap<WritebackDryRunPreviewResponse>(dryRunPreviewWritebackDryRunPreviewGet(params))

export const runWritebackDryRun = (doc_ids: number[]) =>
  unwrap<WritebackDryRunExecuteResponse>(
    dryRunExecuteWritebackDryRunExecutePost({ doc_ids }),
  )

export const executeWritebackNow = (doc_ids: number[]) =>
  unwrap<WritebackExecuteNowResponse>(
    executeWritebackNowWritebackExecuteNowPost({ doc_ids }),
  )

export const executeWritebackDirectForDocument = (
  docId: number,
  params: {
    known_paperless_modified?: string | null
    resolutions?: Record<string, 'skip' | 'use_paperless' | 'use_local'>
  },
) => {
  const payload: WritebackDirectExecuteRequest = {
    known_paperless_modified: params.known_paperless_modified ?? undefined,
    resolutions: params.resolutions ?? {},
  }
  return unwrap<WritebackDirectExecuteResponse>(
    executeWritebackDirectForDocumentWritebackDocumentsDocIdExecuteDirectPost(docId, payload),
  )
}

export const createWritebackJob = (doc_ids: number[]) =>
  unwrap<WritebackJobDetail>(createWritebackJobWritebackJobsPost({ doc_ids }))

export const listWritebackJobs = (limit = 100) =>
  unwrap<WritebackJobListResponse>(listWritebackJobsWritebackJobsGet({ limit }))

export const getWritebackJob = (jobId: number) =>
  unwrap<WritebackJobDetail>(getWritebackJobWritebackJobsJobIdGet(jobId))

export const executeWritebackJob = (jobId: number, dryRun = true) =>
  unwrap<WritebackJobDetail>(
    executeWritebackJobWritebackJobsJobIdExecutePost(jobId, { dry_run: dryRun }),
  )

export const listWritebackHistory = (limit = 100) =>
  unwrap<WritebackJobListResponse>(writebackHistoryWritebackHistoryGet({ limit }))

export const executePendingWritebackJobs = (dryRun = true, limit = 0) =>
  unwrap<WritebackExecutePendingResponse>(
    executePendingWritebackJobsWritebackJobsExecutePendingPost({
      dry_run: dryRun,
      limit,
    }),
  )

export const deleteWritebackJob = (jobId: number) =>
  unwrap<WritebackJobDeleteResult>(deleteWritebackJobWritebackJobsJobIdDelete(jobId))
