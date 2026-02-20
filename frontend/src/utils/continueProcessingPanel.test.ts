import { describe, expect, it } from 'vitest'
import {
  isHighPriorityPreviewDoc,
  priorityScoreForPreviewDoc,
  recommendStrategy,
  sortPreviewDocsByPriority,
  strategyWarningsFor,
  type PreviewDocItem,
} from './continueProcessingPanel'

describe('continueProcessingPanel utils', () => {
  it('scores and sorts preview docs by priority markers', () => {
    const low: PreviewDocItem = {
      doc_id: 2,
      title: 'Low',
      missing_steps: [],
      missing_tasks: ['embeddings_paperless'],
    }
    const high: PreviewDocItem = {
      doc_id: 1,
      title: 'High',
      missing_steps: ['large_document_mode'],
      missing_tasks: ['summary_hierarchical', 'vision_ocr'],
    }
    expect(priorityScoreForPreviewDoc(high)).toBeGreaterThan(priorityScoreForPreviewDoc(low))
    expect(isHighPriorityPreviewDoc(high)).toBe(true)
    expect(sortPreviewDocsByPriority([low, high]).map((d) => d.doc_id)).toEqual([1, 2])
  })

  it('recommends expected strategy for mixed, vision-only, paperless-only and covered states', () => {
    expect(
      recommendStrategy({
        missing_vision_ocr: 1,
        missing_embeddings_vision: 0,
        missing_suggestions_vision: 0,
        missing_page_notes: 0,
        missing_summary_hierarchical: 0,
        missing_embeddings_paperless: 1,
        missing_suggestions_paperless: 0,
      } as never)?.strategy,
    ).toBe('max_coverage')

    expect(
      recommendStrategy({
        missing_vision_ocr: 2,
        missing_embeddings_vision: 1,
        missing_suggestions_vision: 1,
        missing_page_notes: 0,
        missing_summary_hierarchical: 0,
        missing_embeddings_paperless: 0,
        missing_suggestions_paperless: 0,
      } as never)?.strategy,
    ).toBe('vision_first')

    expect(
      recommendStrategy({
        missing_vision_ocr: 0,
        missing_embeddings_vision: 0,
        missing_suggestions_vision: 0,
        missing_page_notes: 0,
        missing_summary_hierarchical: 0,
        missing_embeddings_paperless: 3,
        missing_suggestions_paperless: 2,
      } as never)?.strategy,
    ).toBe('balanced')

    expect(recommendStrategy({} as never)?.strategy).toBe('balanced')
  })

  it('returns warnings for paperless_only and vision_first when opposite-side gaps exist', () => {
    const preview = {
      missing_vision_ocr: 2,
      missing_embeddings_vision: 1,
      missing_suggestions_vision: 0,
      missing_page_notes: 0,
      missing_summary_hierarchical: 0,
      missing_embeddings_paperless: 1,
      missing_suggestions_paperless: 1,
    } as never

    expect(strategyWarningsFor('paperless_only', preview)[0]).toContain('vision-related gaps')
    expect(strategyWarningsFor('vision_first', preview)[0]).toContain('Baseline paperless tasks')
    expect(strategyWarningsFor('balanced', preview)).toEqual([])
  })
})
