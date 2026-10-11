const TASK_LABELS: Record<string, string> = {
  vision_ocr: 'Vision OCR',
  suggestions_paperless: 'Suggestions (Paperless OCR)',
  suggestions_vision: 'Suggestions (Vision OCR)',
  suggest_field: 'New suggestion',
  embeddings_paperless: 'Embeddings (Paperless OCR)',
  embeddings_vision: 'Embeddings (Vision OCR)',
  similarity_index: 'Similarity index',
  evidence_index: 'Evidence index',
  page_notes_paperless: 'Page notes (Paperless OCR)',
  page_notes_vision: 'Page notes (Vision OCR)',
  summary_hierarchical: 'Hierarchical summary',
  sync: 'Sync',
}

/** Human readable name of a queue task; unknown names are made readable (`foo_bar` -> `foo bar`). */
export const taskLabel = (task: string | null | undefined): string => {
  const key = String(task ?? '').trim()
  if (!key) return 'Task'
  return TASK_LABELS[key] ?? key.replace(/_/g, ' ')
}

export type RunningTask = { docId: number | null; label: string }

/** "Vision OCR 3/12 · #2210" style text for one running task. */
export const describeRunningTask = (task: RunningTask): string =>
  task.docId ? `${task.label} · #${task.docId}` : task.label

/** Pill text: counts plus what runs right now (first task), "+n" when more run in parallel. */
export const processingPillLabel = (counts: string, tasks: RunningTask[]): string => {
  const first = tasks[0]
  if (!first) return counts
  const extra = tasks.length > 1 ? ` +${tasks.length - 1}` : ''
  return `${counts} · ${describeRunningTask(first)}${extra}`
}
