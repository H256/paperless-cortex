/* @vitest-environment jsdom */
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import QueueOverviewSection from './QueueOverviewSection.vue'

describe('QueueOverviewSection', () => {
  it('renders queue overview state and emits control actions', async () => {
    const wrapper = mount(QueueOverviewSection, {
      props: {
        status: {
          enabled: true,
          paused: false,
          length: 4,
          total: 9,
          in_progress: 1,
          done: 5,
        },
        running: {
          enabled: true,
          task: {
            doc_id: 42,
            task: 'embeddings_paperless',
          },
          started_at: 1741860000,
        },
        recentTaskRuns: [
          {
            id: 7,
            doc_id: 42,
            task: 'embeddings_paperless',
            status: 'completed',
            attempt: 1,
            error_type: null,
            error_message: null,
            duration_ms: 123,
            started_at: '2026-03-13T10:00:00Z',
            created_at: '2026-03-13T10:00:00Z',
          },
        ],
        taskRunsLoading: false,
        loading: false,
        peekLoading: false,
        busy: false,
        shouldAutoRefreshQueue: true,
        lastRefreshedAt: '2026-03-13T10:01:00Z',
      },
    })

    expect(wrapper.text()).toContain('Queue Manager')
    expect(wrapper.text()).toContain('Auto-refresh active')
    expect(wrapper.text()).toContain('Doc 42')
    expect(wrapper.text()).toContain('embeddings_paperless')

    const buttons = wrapper.findAll('button')
    const refreshButton = buttons.find((button) => button.text().includes('Refresh'))
    const resetButton = buttons.find((button) => button.text().includes('Reset stats'))
    const pauseButton = buttons.find((button) => button.text().includes('Pause'))
    const clearButton = buttons.find((button) => button.text().includes('Clear queue'))
    const reloadRunsButton = buttons.find((button) => button.text().includes('Reload'))

    if (!refreshButton || !resetButton || !pauseButton || !clearButton || !reloadRunsButton) {
      throw new Error('Expected queue overview controls')
    }

    await refreshButton.trigger('click')
    await resetButton.trigger('click')
    await pauseButton.trigger('click')
    await clearButton.trigger('click')
    await reloadRunsButton.trigger('click')

    expect(wrapper.emitted('refresh')).toHaveLength(1)
    expect(wrapper.emitted('reset-stats')).toHaveLength(1)
    expect(wrapper.emitted('pause-queue')).toHaveLength(1)
    expect(wrapper.emitted('clear-queue')).toHaveLength(1)
    expect(wrapper.emitted('reload-task-runs')).toHaveLength(1)
  })
})
