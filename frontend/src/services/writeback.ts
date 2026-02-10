import { request } from './http'

export type WritebackFieldDiff = {
  field: string
  original: unknown
  proposed: unknown
  changed: boolean
}

export type WritebackDryRunItem = {
  doc_id: number
  changed: boolean
  changed_fields: string[]
  title: WritebackFieldDiff
  document_date: WritebackFieldDiff
  correspondent: WritebackFieldDiff
  tags: WritebackFieldDiff
  note: WritebackFieldDiff
}

export type WritebackDryRunPreviewResponse = {
  count: number
  page: number
  page_size: number
  items: WritebackDryRunItem[]
}

export type WritebackDryRunExecuteResponse = {
  docs_selected: number
  docs_changed: number
  calls: Array<{
    doc_id: number
    method: string
    path: string
    payload: Record<string, unknown>
  }>
}

export type WritebackJobSummary = {
  id: number
  status: string
  dry_run: boolean
  docs_selected: number
  docs_changed: number
  calls_count: number
  created_at?: string | null
  started_at?: string | null
  finished_at?: string | null
  error?: string | null
}

export type WritebackJobDetail = WritebackJobSummary & {
  doc_ids: number[]
  calls: Array<{
    doc_id: number
    method: string
    path: string
    payload: Record<string, unknown>
  }>
}

export type WritebackJobListResponse = {
  items: WritebackJobSummary[]
}

export const getWritebackDryRunPreview = (params: {
  page: number
  page_size: number
  only_changed?: boolean
  doc_id?: number
}) =>
  request<WritebackDryRunPreviewResponse>('/writeback/dry-run/preview', {
    params,
  })

export const runWritebackDryRun = (doc_ids: number[]) =>
  request<WritebackDryRunExecuteResponse>('/writeback/dry-run/execute', {
    method: 'POST',
    body: { doc_ids },
  })

export const createWritebackJob = (doc_ids: number[]) =>
  request<WritebackJobDetail>('/writeback/jobs', {
    method: 'POST',
    body: { doc_ids },
  })

export const listWritebackJobs = (limit = 100) =>
  request<WritebackJobListResponse>('/writeback/jobs', { params: { limit } })

export const getWritebackJob = (jobId: number) =>
  request<WritebackJobDetail>(`/writeback/jobs/${jobId}`)

export const executeWritebackJob = (jobId: number, dryRun = true) =>
  request<WritebackJobDetail>(`/writeback/jobs/${jobId}/execute`, {
    method: 'POST',
    body: { dry_run: dryRun },
  })

export const listWritebackHistory = (limit = 100) =>
  request<WritebackJobListResponse>('/writeback/history', { params: { limit } })
