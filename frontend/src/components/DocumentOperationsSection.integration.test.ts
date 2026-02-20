/* @vitest-environment jsdom */
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import DocumentOperationsSection from './DocumentOperationsSection.vue'

const baseProps = {
  continuePipelineLoading: false,
  continueQueuedWaiting: false,
  hasActiveTaskRuns: false,
  docOpsLoading: false,
  pipelineStatusLoading: false,
  pipelineStatusError: '',
  processingDoneCount: 1,
  processingRequiredCount: 2,
  pipelinePreferredSource: 'paperless_ocr',
  isLargeDocumentMode: false,
  largeDocumentHint: 'Standard mode',
  processingStatusItems: [
    { label: 'Vision Ocr', state: 'done' as const, detail: '' },
    { label: 'Summary Hierarchical', state: 'missing' as const, detail: 'missing' },
  ],
  pipelineFanoutLoading: false,
  pipelineFanoutError: '',
  pipelineFanoutItems: [],
  timelineStatusFilter: '',
  timelineQueryFilter: '',
  taskRunsLoading: false,
  taskRunsError: '',
  taskRuns: [
    {
      id: 1,
      task: 'summary_hierarchical',
      status: 'failed',
      started_at: '2026-02-20T19:00:00Z',
      attempt: 1,
      checkpoint: { step: 'aggregate' },
      error_type: 'test_error',
      error_message: 'test failure',
      source: 'vision_ocr',
    },
  ],
  docCleanupClearFirst: false,
  docOpsMessage: '',
  operationActions: [{ task: 'vision_ocr', label: 'Queue vision OCR', tooltip: 'x' }],
  toTitle: (value: string | null | undefined) => String(value || ''),
  processingBadgeClass: () => '',
  processingStateLabel: () => '',
  fanoutStatusClass: () => '',
  toRelativeTime: () => 'now',
  toDateTime: () => 'now',
  checkpointLabel: () => 'checkpoint',
  embeddingTelemetryLabel: () => '',
  compactErrorMessage: () => 'compact',
}

describe('DocumentOperationsSection emits', () => {
  it('emits main actions and filter updates', async () => {
    const wrapper = mount(DocumentOperationsSection, { props: baseProps })

    await wrapper.find('button[title*="enqueues only those tasks"]').trigger('click')
    expect(wrapper.emitted('continue-pipeline')).toBeTruthy()

    const searchInput = wrapper.find('input[placeholder="task/error..."]')
    await searchInput.setValue('failed')
    expect(wrapper.emitted('update:timeline-query-filter')?.[0]).toEqual(['failed'])

    const statusSelect = wrapper.find('select')
    await statusSelect.setValue('failed')
    expect(wrapper.emitted('update:timeline-status-filter')?.[0]).toEqual(['failed'])

    await wrapper.find('button[title="Cleans stored page texts (e.g., line wraps or HTML noise) and updates clean fields."]').trigger('click')
    expect(wrapper.emitted('run-doc-cleanup')).toBeTruthy()

    await wrapper.find('button[title="Deletes local intelligence data for this document, resyncs from Paperless, and enqueues processing."]').trigger('click')
    expect(wrapper.emitted('open-reset-confirm')).toBeTruthy()
  })
})
