/* @vitest-environment jsdom */
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ContinueProcessingDiagnosticsSection from './ContinueProcessingDiagnosticsSection.vue'

const baseProps = {
  showDiagnostics: true,
  processPreviewLoading: false,
  processPreview: { docs: 2, missing_docs: 1 } as never,
  coverageItems: [{ key: 'overall', label: 'Overall docs with gaps', missing: 1 }],
  showDetailedCounters: false,
  showOnlyNonZeroCounters: true,
  visibleDetailedCounters: [{ key: 'vision', label: 'Missing vision OCR', value: 2 }],
  previewDocs: [{ doc_id: 7, title: 'Doc 7', missing_steps: ['large'], missing_tasks: ['vision_ocr'] }],
  prioritizedPreviewDocs: [
    { doc_id: 7, title: 'Doc 7', missing_steps: ['large'], missing_tasks: ['vision_ocr'] },
  ],
  highPriorityPreviewCount: 1,
  executionPlanSteps: ['Sync first', 'Enqueue missing work'],
  executionScopeItems: [{ key: 'sync', label: 'Paperless sync', included: true }],
  queueEnabled: true,
  queueLengthLabel: '3',
  processingActive: false,
}

describe('ContinueProcessingDiagnosticsSection', () => {
  it('emits toggle and open-doc actions through the extracted seam', async () => {
    const wrapper = mount(ContinueProcessingDiagnosticsSection, { props: baseProps })

    await wrapper.get('button[title="Open document 7"]').trigger('click')
    expect(wrapper.emitted('open-doc')).toEqual([[7]])

    const toggleButton = wrapper
      .findAll('button')
      .find((button) => button.text().includes('Show details'))
    expect(toggleButton).toBeTruthy()
    await toggleButton!.trigger('click')
    expect(wrapper.emitted('toggle-detailed-counters')).toBeTruthy()
  })
})
