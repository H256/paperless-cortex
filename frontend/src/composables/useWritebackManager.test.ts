/* @vitest-environment jsdom */
import { describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'

const mocks = vi.hoisted(() => ({
  createWritebackJob: vi.fn(async () => ({ id: 1 })),
  deleteWritebackJob: vi.fn(async () => ({ removed: true })),
  executePendingWritebackJobs: vi.fn(),
  executeWritebackJob: vi.fn(async () => ({ id: 1, status: 'completed', doc_ids: [] })),
  getWritebackDryRunPreview: vi.fn(async () => ({ items: [] })),
  listWritebackHistory: vi.fn(async () => ({ items: [] })),
  listWritebackJobs: vi.fn(async () => ({ items: [] })),
  runWritebackDryRun: vi.fn(async () => ({ items: [] })),
}))

vi.mock('../services/writeback', () => ({
  ...mocks,
}))

import { useWritebackManager } from './useWritebackManager'

const mountManager = () => {
  const queryClient = new QueryClient()
  const Host = defineComponent({
    setup() {
      return { manager: useWritebackManager() }
    },
    render() {
      return h('div')
    },
  })
  const wrapper = mount(Host, { global: { plugins: [[VueQueryPlugin, { queryClient }]] } })
  return { wrapper, queryClient }
}

describe('useWritebackManager.executeAllMutation', () => {
  it('preserves prior per-job results (does not wipe the panel) on a failed bulk run', async () => {
    const { wrapper } = mountManager()
    const manager = (wrapper.vm as unknown as { manager: ReturnType<typeof useWritebackManager> })
      .manager

    // Simulate a prior successful bulk run so the panel has data.
    manager.lastExecuteAllResults.value = [
      {
        job_id: 1,
        status: 'completed',
        dry_run: false,
        docs_selected: 2,
        docs_changed: 1,
        calls_count: 1,
        doc_ids: [42],
        error: null,
      },
    ]

    // Backend 500 partial-write failure mode.
    mocks.executePendingWritebackJobs.mockRejectedValueOnce(new Error('upstream writeback failed'))

    await expect(manager.executeAllMutation.mutateAsync({ dryRun: false, limit: 0 })).rejects.toThrow(
      'upstream writeback failed',
    )

    // The panel must NOT be wiped on failure, so the user can still see which
    // documents were processed before the run failed partway through.
    expect(manager.lastExecuteAllResults.value.length).toBe(1)
    expect(manager.lastExecuteAllResults.value[0]?.job_id).toBe(1)
  })
})
