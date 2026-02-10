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
