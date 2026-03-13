// @vitest-environment jsdom
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import DocumentsHeaderSection from './DocumentsHeaderSection.vue'

describe('DocumentsHeaderSection', () => {
  it('renders counts, search label, and re-emits toolbar actions', async () => {
    const wrapper = mount(DocumentsHeaderSection, {
      props: {
        visibleCount: 5,
        totalCount: 12,
        searchLabel: 'invoice',
        stats: {
          total: 12,
          embeddings: 8,
          suggestions: 7,
          vision: 4,
          processed: 6,
          unprocessed: 6,
          fully_processed: 3,
        },
        queuedCount: 2,
        isProcessing: false,
        syncStatus: { status: 'running', processed: 2, total: 12 },
        embedStatus: { status: 'running', processed: 3, total: 8 },
        hasQueuedWork: true,
        showCancel: true,
        progressPercent: 20,
        etaText: '1m',
        embedLabel: 'Embeddings',
        processingProcessed: 3,
        processingTotal: 8,
        processingPercent: 38,
        processingEtaText: '2m',
        lastRunText: 'just now',
      },
    })

    expect(wrapper.text()).toContain('Showing 5 of 12 synced documents')
    expect(wrapper.text()).toContain('for "invoice"')

    const buttons = wrapper.findAll('button')
    await buttons.find((button) => button.text().includes('Continue processing'))?.trigger('click')
    await buttons.find((button) => button.text().includes('Cancel processing'))?.trigger('click')

    expect(wrapper.emitted('open-preview')).toHaveLength(1)
    expect(wrapper.emitted('cancel-processing')).toHaveLength(1)
  })
})
