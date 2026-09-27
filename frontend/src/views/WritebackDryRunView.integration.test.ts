/* @vitest-environment jsdom */
import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

let WritebackDryRunView: unknown

const push = vi.fn()

vi.mock('../stores/toastStore', () => ({
  useToastStore: () => ({ push }),
}))

const mutateAsync = vi.fn()
const reloadJobs = vi.fn(async () => undefined)
const reloadHistory = vi.fn(async () => undefined)
const removeDocsFromSelection = vi.fn()

vi.mock('../composables/useWritebackManager', () => ({
  useWritebackManager: () => ({
    onlyChanged: ref(true),
    selectedSet: ref(new Set<number>()),
    selectedIds: ref<number[]>([]),
    previewItems: ref([]),
    jobs: ref([]),
    historyItems: ref([]),
    pendingCount: ref(2),
    lastExecuteAllResults: ref([]),
    previewQuery: { isFetching: ref(false), data: ref({ items: [] }) },
    jobsQuery: { isFetching: ref(false), data: ref({ items: [] }) },
    historyQuery: { isFetching: ref(false), data: ref({ items: [] }) },
    runDryRunMutation: { mutateAsync: vi.fn(), isPending: ref(false) },
    enqueueMutation: { mutateAsync: vi.fn(), isPending: ref(false) },
    executeJobMutation: { mutateAsync: vi.fn(), isPending: ref(false) },
    executeAllMutation: { mutateAsync, isPending: ref(false) },
    deleteJobMutation: { mutateAsync: vi.fn(), isPending: ref(false) },
    toggleSelect: vi.fn(),
    selectAllChanged: vi.fn(),
    clearSelection: vi.fn(),
    reloadPreview: vi.fn(async () => undefined),
    reloadJobs,
    reloadHistory,
    removeDocsFromSelection,
  }),
}))

describe('WritebackDryRunView executeAllPending error path', () => {
  beforeAll(async () => {
    WritebackDryRunView = (await import('./WritebackDryRunView.vue')).default
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('keeps the results panel, refreshes jobs/history, and warns about a partial write on failure', async () => {
    // Seed prior per-job results so the panel has data before the failed run.
    mutateAsync.mockRejectedValueOnce(new Error('upstream writeback failed'))

    const wrapper = mount(WritebackDryRunView as never)
    const vm = wrapper.vm as unknown as {
      lastExecuteAllResults: Array<{ job_id: number }>
    }
    vm.lastExecuteAllResults = [
      { job_id: 1 },
      { job_id: 2 },
    ]

    // The "Run all pending" button lives in the Queue tab; switch to it first.
    const queueTab = wrapper
      .findAll('button')
      .find((button) => button.text().trim() === 'Queue')
    if (!queueTab) {
      throw new Error('Expected the "Queue" tab button')
    }
    await queueTab.trigger('click')
    await new Promise((resolve) => setTimeout(resolve, 0))

    // The "Run all pending (dry-run)" button triggers executeAllPending(true).
    const runAllButton = wrapper
      .findAll('button')
      .find((button) => button.text().includes('Run all pending'))
    if (!runAllButton) {
      throw new Error('Expected the "Run all pending" button')
    }
    await runAllButton.trigger('click')
    // Let the async handler (toast + loadJobs/loadHistory) settle.
    await new Promise((resolve) => setTimeout(resolve, 0))

    // The panel must NOT be wiped on failure.
    expect(vm.lastExecuteAllResults.length).toBe(2)

    // Real job/history state must be refreshed so partial writes are visible.
    expect(reloadJobs).toHaveBeenCalled()
    expect(reloadHistory).toHaveBeenCalled()

    // A partial-write warning must be surfaced alongside the error toast.
    const messages = push.mock.calls.map((call) => String(call[0]))
    expect(messages.some((message) => message.includes('partial write'))).toBe(true)
  })
})
