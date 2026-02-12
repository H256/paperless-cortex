const STAGE_LABELS: Record<string, string> = {
  vision_ocr: 'Vision OCR',
  embedding_chunks: 'Embeddings',
  page_notes: 'Page notes',
  summary_sections: 'Hier summary',
  summary_global: 'Global summary',
}

const normalizeStage = (value: unknown) => {
  if (typeof value !== 'string') return 'progress'
  const stage = value.trim()
  return stage || 'progress'
}

const toStageLabel = (stage: string) => STAGE_LABELS[stage] || stage

export const hasResumeMarker = (checkpoint?: Record<string, unknown> | null) =>
  Boolean(checkpoint && typeof checkpoint === 'object' && checkpoint.resume_from)

export const formatCheckpointLabel = (
  checkpoint?: Record<string, unknown> | null,
  fallback = '-',
) => {
  if (!checkpoint || typeof checkpoint !== 'object') return fallback
  const stage = normalizeStage(checkpoint.stage)
  const current = typeof checkpoint.current === 'number' ? checkpoint.current : null
  const total = typeof checkpoint.total === 'number' ? checkpoint.total : null
  const label = toStageLabel(stage)
  if (current != null && total != null && total > 0) return `${label} ${current}/${total}`
  if (current != null) return `${label} ${current}`
  return label
}
