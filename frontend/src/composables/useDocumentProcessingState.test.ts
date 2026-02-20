import { describe, expect, it } from 'vitest'
import { ref } from 'vue'
import {
  fanoutStatusClass,
  processingBadgeClass,
  processingStateLabel,
  useDocumentProcessingState,
} from './useDocumentProcessingState'

describe('useDocumentProcessingState', () => {
  it('derives processing and active-run labels from pipeline/task state', () => {
    const pipelineStatus = ref({
      steps: [
        { key: 'vision_ocr', required: true, done: true, detail: '' },
        { key: 'summary_hierarchical', required: true, done: false, detail: 'missing summary' },
        { key: 'page_notes_vision', required: false, done: false, detail: '' },
      ],
      preferred_source: 'vision_ocr',
      is_large_document: true,
    })
    const pipelineFanout = ref({ items: [{ task: 'embeddings_vision' }] })
    const taskRuns = ref([
      { task: 'summary_hierarchical', status: 'running', checkpoint: { step: 'aggregate' } },
    ])
    const continueQueuedWaiting = ref(false)

    const state = useDocumentProcessingState(
      { pipelineStatus, pipelineFanout, taskRuns, continueQueuedWaiting },
      (checkpoint) => String(checkpoint?.step || '-'),
    )

    expect(state.processingStatusItems.value).toHaveLength(3)
    expect(state.processingDoneCount.value).toBe(1)
    expect(state.processingRequiredCount.value).toBe(2)
    expect(state.pipelinePreferredSource.value).toBe('vision_ocr')
    expect(state.isLargeDocumentMode.value).toBe(true)
    expect(state.largeDocumentHint.value).toContain('Large-document mode active')
    expect(state.hasActiveTaskRuns.value).toBe(true)
    expect(state.activeRunLabel.value).toBe('summary_hierarchical (aggregate)')
    expect(state.pipelineFanoutItems.value).toEqual([{ task: 'embeddings_vision' }])
  })

  it('keeps auto-refresh active while waiting for queued pickup without active task runs', () => {
    const state = useDocumentProcessingState(
      {
        pipelineStatus: ref({ steps: [] }),
        pipelineFanout: ref({ items: [] }),
        taskRuns: ref([]),
        continueQueuedWaiting: ref(true),
      },
      () => '-',
    )
    expect(state.hasActiveTaskRuns.value).toBe(false)
    expect(state.shouldAutoRefreshTimeline.value).toBe(true)
  })
})

describe('useDocumentProcessingState helpers', () => {
  it('maps state and status labels/classes', () => {
    expect(processingStateLabel('done')).toBe('Done')
    expect(processingBadgeClass('missing')).toContain('amber')
    expect(fanoutStatusClass('retrying')).toContain('indigo')
    expect(fanoutStatusClass('failed')).toContain('rose')
  })
})
