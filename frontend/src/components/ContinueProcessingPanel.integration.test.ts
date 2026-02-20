/* @vitest-environment jsdom */
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ContinueProcessingPanel from './ContinueProcessingPanel.vue'

const baseProps = {
  syncStatus: { status: 'idle', total: 0, processed: 0, incremental: true } as never,
  progressPercent: 0,
  etaText: '-',
  processPreviewLoading: false,
  processPreview: null,
  processOptions: { includeSync: true, strategy: 'balanced' as const },
  batchIndex: 0,
  batchOptions: [10, 'All'] as const,
  batchLabel: '10',
  processStartResult: null,
  processStartLoading: false,
  syncing: false,
  isSyncingNow: false,
  queueEnabled: true,
  queueLength: 0,
  processingActive: false,
}

describe('ContinueProcessingPanel', () => {
  it('emits update events instead of mutating props', async () => {
    const wrapper = mount(ContinueProcessingPanel, { props: baseProps })

    const checkbox = wrapper.find('input[type="checkbox"]')
    await checkbox.setValue(false)
    expect(wrapper.emitted('update:includeSync')).toBeTruthy()

    const select = wrapper.find('select')
    await select.setValue('vision_first')
    expect(wrapper.emitted('update:strategy')).toBeTruthy()
  })
})
