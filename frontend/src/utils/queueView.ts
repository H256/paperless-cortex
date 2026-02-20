export type QueueListItem = { doc_id?: number | null; task?: string | null; raw?: string | null }

const TASK_MAP: Record<string, { label: string; description: string }> = {
  sync: { label: 'Sync document', description: 'Fetch latest metadata from Paperless.' },
  vision_ocr: { label: 'Vision OCR', description: 'Run OCR on the document pages.' },
  embeddings_paperless: {
    label: 'Baseline embeddings',
    description: 'Embed text from Paperless OCR.',
  },
  embeddings_vision: {
    label: 'Vision embeddings',
    description: 'Embed text from Vision OCR pages.',
  },
  suggestions_paperless: {
    label: 'AI suggestions (baseline)',
    description: 'Generate metadata suggestions from OCR.',
  },
  suggestions_vision: {
    label: 'AI suggestions (vision)',
    description: 'Generate metadata suggestions from vision OCR.',
  },
  suggest_field: {
    label: 'Field variants',
    description: 'Suggest alternative values for a field.',
  },
  full: { label: 'Full pipeline', description: 'Sync, OCR, embeddings, and suggestions.' },
}

export const queueItemTitle = (item: QueueListItem) => {
  if (item.doc_id != null) {
    const key = item.task || 'full'
    const label = TASK_MAP[key]?.label || key
    return `Doc ${item.doc_id} - ${label}`
  }
  return item.raw || 'Unknown item'
}

export const queueItemDescription = (item: QueueListItem) => {
  const key = item.task || 'full'
  if (item.doc_id != null && TASK_MAP[key]) return TASK_MAP[key].description
  return item.raw ? 'Custom queue payload' : 'Unknown queue item'
}

export const queueFormatStartedAt = (unixTs: number) => new Date(unixTs * 1000).toLocaleString()

export const queueFormatRuntime = (unixTs: number) => {
  const seconds = Math.max(0, Math.floor(Date.now() / 1000) - unixTs)
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  if (mins <= 0) return `${secs}s`
  if (mins < 60) return `${mins}m ${secs}s`
  const hours = Math.floor(mins / 60)
  const remMins = mins % 60
  return `${hours}h ${remMins}m`
}

export const queueFormatDueIn = (value?: number | null) => {
  if (value == null) return '-'
  const seconds = Math.max(0, Math.floor(value))
  if (seconds < 60) return `${seconds}s`
  const mins = Math.floor(seconds / 60)
  const rem = seconds % 60
  return `${mins}m ${rem}s`
}

export const queueCompactMessage = (message?: string | null) => {
  if (!message) return '-'
  const normalized = message.replace(/\s+/g, ' ').trim()
  return normalized.length > 100 ? `${normalized.slice(0, 97)}...` : normalized
}

export const delayedTaskLabel = (item: { task?: unknown }) => {
  const task = item.task
  if (!task || typeof task !== 'object') return 'unknown'
  const value = (task as Record<string, unknown>).task
  return String(value || 'unknown')
}

export const delayedDocId = (item: { task?: unknown }) => {
  const task = item.task
  if (!task || typeof task !== 'object') return '-'
  const value = (task as Record<string, unknown>).doc_id
  return value == null ? '-' : String(value)
}
