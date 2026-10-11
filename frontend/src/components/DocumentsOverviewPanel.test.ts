// @vitest-environment jsdom
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import DocumentsOverviewPanel from './DocumentsOverviewPanel.vue'

const props = {
  stats: {
    total: 2203,
    processed: 2203,
    unprocessed: 0,
    embeddings: 2203,
    vision: 2200,
    suggestions: 2201,
    fully_processed: 2199,
  },
  queuedCount: 3,
  isProcessing: false,
  syncStatus: { status: 'idle', processed: 0, total: 0 },
  embedStatus: { status: 'idle', processed: 0, total: 0 },
  hasQueuedWork: false,
  progressPercent: 0,
  etaText: '--',
  embedLabel: 'Embedding',
  processingProcessed: 0,
  processingTotal: 0,
  processingPercent: 0,
  processingEtaText: '--',
  lastRunText: '--',
}

describe('DocumentsOverviewPanel', () => {
  it('shows the counters in one compact row without the duplicate "Processed*"', () => {
    const wrapper = mount(DocumentsOverviewPanel, { props: props as never })
    const text = wrapper.get('[data-testid="overview-stats"]').text()

    for (const label of ['Synced', 'Queued', 'Embeddings', 'Vision OCR', 'Suggestions', 'Fully processed', 'Pending']) {
      expect(text).toContain(label)
    }
    expect(text).toContain('2203')
    expect(text).not.toContain('Processed*')
    wrapper.unmount()
  })
})
