// @vitest-environment jsdom
import { mount } from '@vue/test-utils'
import { reactive, ref } from 'vue'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

let QueueView: unknown

const route = reactive({
  path: '/queue',
  fullPath: '/queue',
  query: {} as Record<string, string>,
})

const router = {
  push: vi.fn(async () => undefined),
}

vi.mock('vue-router', () => ({
  useRoute: () => route,
  useRouter: () => router,
}))

vi.mock('../composables/useAutoRefresh', () => ({
  useAutoRefresh: vi.fn(),
}))

vi.mock('../stores/toastStore', () => ({
  useToastStore: () => ({
    push: vi.fn(),
  }),
}))

const refresh = vi.fn(async () => undefined)
const loadPeek = vi.fn(async () => undefined)
const loadTaskRuns = vi.fn(async () => undefined)
const loadDelayed = vi.fn(async () => undefined)
const loadDlq = vi.fn(async () => undefined)
const retryFailedRuns = vi.fn(async () => undefined)
const clearDlq = vi.fn(async () => undefined)
const requeueDlqItem = vi.fn(async () => undefined)
const moveTop = vi.fn(async () => undefined)
const moveItem = vi.fn(async () => undefined)
const moveBottom = vi.fn(async () => undefined)
const removeItem = vi.fn(async () => undefined)

vi.mock('../composables/useQueueManager', () => ({
  useQueueManager: () => ({
    status: ref({
      enabled: true,
      paused: false,
      length: 2,
      total: 7,
      in_progress: 1,
      done: 4,
    }),
    running: ref({
      enabled: true,
      task: { doc_id: 42, task: 'embeddings_paperless' },
      started_at: 1741860000,
    }),
    peekItems: ref([
      { doc_id: 42, task: 'embeddings_paperless', raw: '{"doc_id":42}' },
      { doc_id: 84, task: 'sync', raw: '{"doc_id":84}' },
    ]),
    taskRuns: ref([
      {
        id: 9,
        doc_id: 42,
        task: 'embeddings_paperless',
        status: 'failed',
        attempt: 1,
        error_type: 'VECTOR_CHUNKS_MISSING',
        error_message: 'missing vectors',
        checkpoint: null,
        duration_ms: 120,
        started_at: '2026-03-13T10:00:00Z',
        created_at: '2026-03-13T10:00:00Z',
      },
    ]),
    taskRunsCount: ref(1),
    taskRunsLoading: ref(false),
    peekLimit: ref(20),
    taskRunsLimit: ref(50),
    taskRunsDocId: ref(''),
    taskRunsTask: ref(''),
    taskRunsStatus: ref(''),
    taskRunsErrorType: ref(''),
    taskRunsQuery: ref(''),
    delayedItems: ref([]),
    delayedLoading: ref(false),
    delayedLimit: ref(50),
    dlqItems: ref([]),
    dlqLoading: ref(false),
    dlqLimit: ref(50),
    loading: ref(false),
    peekLoading: ref(false),
    busy: ref(false),
    lastRefreshedAt: ref('2026-03-13T10:01:00Z'),
    error: ref(''),
    refresh,
    loadPeek,
    loadTaskRuns,
    loadDelayed,
    loadDlq,
    clearDlq,
    requeueDlqItem,
    retryFailedRuns,
    clearQueue: vi.fn(async () => undefined),
    resetStats: vi.fn(async () => undefined),
    pauseQueue: vi.fn(async () => undefined),
    resumeQueue: vi.fn(async () => undefined),
    moveItem,
    moveTop,
    moveBottom,
    removeItem,
  }),
}))

describe('QueueView', () => {
  beforeAll(async () => {
    QueueView = (await import('./QueueView.vue')).default
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('wires queue actions, filtering, and document navigation through the view', async () => {
    const wrapper = mount(QueueView as never)

    expect(refresh).toHaveBeenCalled()

    const filter = wrapper.get('input[placeholder="Filter"]')
    await filter.setValue('42')
    expect(wrapper.text()).toContain('Doc 42')
    expect(wrapper.text()).not.toContain('Doc 84')

    await wrapper.get('button[title="Move down"]').trigger('click')
    await wrapper.get('button[title="Remove"]').trigger('click')

    expect(moveItem).toHaveBeenCalledWith(0, 1)
    expect(removeItem).toHaveBeenCalledWith(0)

    await wrapper.get('tbody button').trigger('click')
    expect(router.push).toHaveBeenCalledWith('/documents/42')

    const retryButton = wrapper
      .findAll('button')
      .find((button) => button.text().includes('Retry failed (filtered)'))
    if (!retryButton) {
      throw new Error('Expected retry button')
    }
    await retryButton.trigger('click')
    expect(retryFailedRuns).toHaveBeenCalled()
  })
})
