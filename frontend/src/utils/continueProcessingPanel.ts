import type { ProcessMissingResponse } from '@/api/generated/model'

export type ProcessStrategy = 'balanced' | 'paperless_only' | 'vision_first' | 'max_coverage'

export type PreviewDocItem = {
  doc_id: number
  title: string
  missing_steps: string[]
  missing_tasks: string[]
}

const PRIORITY_TASK_MARKERS = [
  'page_notes',
  'summary_hierarchical',
  'suggestions_vision',
  'vision_ocr',
  'embeddings_vision',
]

export const priorityScoreForPreviewDoc = (item: PreviewDocItem) => {
  let score = 0
  for (const task of item.missing_tasks || []) {
    const normalized = String(task || '').toLowerCase()
    if (PRIORITY_TASK_MARKERS.some((marker) => normalized.includes(marker))) score += 2
  }
  if ((item.missing_steps || []).some((step) => String(step || '').toLowerCase().includes('large'))) score += 3
  return score
}

export const isHighPriorityPreviewDoc = (item: PreviewDocItem) => priorityScoreForPreviewDoc(item) >= 3

export const sortPreviewDocsByPriority = (items: PreviewDocItem[]) =>
  [...items].sort((a, b) => {
    const scoreDiff = priorityScoreForPreviewDoc(b) - priorityScoreForPreviewDoc(a)
    if (scoreDiff !== 0) return scoreDiff
    const taskDiff = (b.missing_tasks?.length || 0) - (a.missing_tasks?.length || 0)
    if (taskDiff !== 0) return taskDiff
    return a.doc_id - b.doc_id
  })

export const recommendStrategy = (
  preview: ProcessMissingResponse | null | undefined,
): null | { strategy: ProcessStrategy; reason: string } => {
  if (!preview) return null
  const visionGaps =
    Number(preview.missing_vision_ocr ?? 0) +
    Number(preview.missing_embeddings_vision ?? 0) +
    Number(preview.missing_suggestions_vision ?? 0) +
    Number(preview.missing_page_notes ?? 0) +
    Number(preview.missing_summary_hierarchical ?? 0)
  const paperlessGaps =
    Number(preview.missing_embeddings_paperless ?? 0) +
    Number(preview.missing_suggestions_paperless ?? 0)
  const largeGaps = Number(preview.missing_page_notes ?? 0) + Number(preview.missing_summary_hierarchical ?? 0)

  if (largeGaps > 0 || (visionGaps > 0 && paperlessGaps > 0)) {
    return { strategy: 'max_coverage', reason: 'large-doc or mixed source gaps detected' }
  }
  if (visionGaps > 0) return { strategy: 'vision_first', reason: 'vision pipeline gaps dominate' }
  if (paperlessGaps > 0) return { strategy: 'balanced', reason: 'baseline tasks remain' }
  return { strategy: 'balanced', reason: 'already mostly covered' }
}

export const strategyWarningsFor = (
  strategy: ProcessStrategy,
  preview: ProcessMissingResponse | null | undefined,
): string[] => {
  if (!preview) return []
  const warnings: string[] = []
  if (strategy === 'paperless_only') {
    const visionGaps =
      Number(preview.missing_vision_ocr ?? 0) +
      Number(preview.missing_embeddings_vision ?? 0) +
      Number(preview.missing_suggestions_vision ?? 0) +
      Number(preview.missing_page_notes ?? 0) +
      Number(preview.missing_summary_hierarchical ?? 0)
    if (visionGaps > 0) {
      warnings.push(
        `Selected strategy may leave ${visionGaps} vision-related gaps unresolved (switch to Balanced, Vision first, or Max coverage to include them).`,
      )
    }
  }
  if (strategy === 'vision_first') {
    const baselineGaps =
      Number(preview.missing_embeddings_paperless ?? 0) +
      Number(preview.missing_suggestions_paperless ?? 0)
    if (baselineGaps > 0) {
      warnings.push(
        `Baseline paperless tasks still missing: ${baselineGaps}. Consider Balanced or Max coverage if baseline parity is required.`,
      )
    }
  }
  return warnings
}
