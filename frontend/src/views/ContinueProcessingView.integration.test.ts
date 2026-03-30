// @vitest-environment jsdom
import { mount } from '@vue/test-utils'
import { reactive, ref } from 'vue'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

let ContinueProcessingView: unknown
const toastPush = vi.fn()

const route = reactive({
  path: '/processing/continue',
  query: {} as Record<string, string>,
})

const router = {
  push: vi.fn(async () => undefined),
  replace: vi.fn(async () => undefined),
}

vi.mock('vue-router', () => ({
  useRoute: () => route,
  useRouter: () => router,
}))

vi.mock('../stores/toastStore', () => ({
  useToastStore: () => ({
    push: toastPush,
  }),
}))

const refreshOverview = vi.fn(async () => undefined)
const openPreview = vi.fn(async () => undefined)
const refreshProcessPreview = vi.fn(async () => undefined)
const startFromPreviewRequest = vi.fn(async () => undefined)
const clearPreviewState = vi.fn()

vi.mock('../composables/useProcessingOverview', () => ({
  useProcessingOverview: () => ({
    syncStatus: ref({ status: 'idle', processed: 0, total: 0, started_at: null, eta_seconds: null }),
    embedStatus: ref({ status: 'idle', processed: 0, total: 0, started_at: null, eta_seconds: null }),
    queueStatus: ref({ enabled: true, length: 2 }),
    refresh: refreshOverview,
  }),
}))

vi.mock('../composables/useContinueProcessing', () => ({
  useContinueProcessing: () => ({
    processPreview: ref(null),
    processPreviewLoading: ref(false),
    processStartResult: ref(null),
    processStartLoading: ref(false),
    showPreviewModal: ref(false),
    openPreview,
    refreshProcessPreview,
    startFromPreview: startFromPreviewRequest,
    closePreview: clearPreviewState,
  }),
}))

vi.mock('../composables/useContinueProcessOptions', () => ({
  useContinueProcessOptions: () => ({
    processOptions: reactive({
      includeSync: true,
      strategy: 'balanced',
    }),
    batchOptions: [10, 'All'],
    batchIndex: ref(0),
    batchLabel: ref('10'),
    processParams: () => ({
      include_sync: true,
      strategy: 'balanced',
      limit: 10,
    }),
  }),
}))

vi.mock('../composables/usePreviewAutoRefresh', () => ({
  usePreviewAutoRefresh: vi.fn(),
}))

vi.mock('../composables/useProcessingMetrics', () => ({
  useProcessingMetrics: () => ({
    isProcessing: ref(false),
    isSyncingNow: ref(false),
    progressPercent: ref(0),
    etaText: ref('--'),
  }),
}))

describe('ContinueProcessingView', () => {
  beforeAll(async () => {
    ContinueProcessingView = (await import('./ContinueProcessingView.vue')).default
  })

  afterEach(() => {
    route.query = {}
    vi.clearAllMocks()
  })

  it('hydrates preview on mount and routes panel actions through the view', async () => {
    const wrapper = mount(ContinueProcessingView as never, {
      global: {
        stubs: {
          ContinueProcessingPanel: {
            template: `
              <div>
                <button data-test="start" @click="$emit('start')">start</button>
                <button data-test="open-doc" @click="$emit('open-doc', 11)">doc</button>
                <button data-test="open-queue" @click="$emit('open-queue')">queue</button>
                <button data-test="open-logs" @click="$emit('open-logs')">logs</button>
                <button data-test="close" @click="$emit('close')">close</button>
              </div>
            `,
          },
        },
      },
    })

    await Promise.resolve()

    expect(openPreview).toHaveBeenCalled()
    expect(refreshOverview).toHaveBeenCalled()

    await wrapper.get('[data-test="start"]').trigger('click')
    expect(startFromPreviewRequest).toHaveBeenCalled()

    await wrapper.get('[data-test="open-doc"]').trigger('click')
    await wrapper.get('[data-test="open-queue"]').trigger('click')
    await wrapper.get('[data-test="open-logs"]').trigger('click')
    await wrapper.get('[data-test="close"]').trigger('click')

    expect(clearPreviewState).toHaveBeenCalled()
    expect(router.push).toHaveBeenCalledWith('/documents/11')
    expect(router.push).toHaveBeenCalledWith('/queue')
    expect(router.push).toHaveBeenCalledWith('/logs')
    expect(router.push).toHaveBeenCalledWith('/documents')
  })

  it('blocks navigation for invalid preview doc ids', async () => {
    const wrapper = mount(ContinueProcessingView as never, {
      global: {
        stubs: {
          ContinueProcessingPanel: {
            template: '<button data-test="open-doc" @click="$emit(\'open-doc\', Number.NaN)">doc</button>',
          },
        },
      },
    })

    await Promise.resolve()
    vi.clearAllMocks()

    await wrapper.get('[data-test="open-doc"]').trigger('click')

    expect(router.push).not.toHaveBeenCalled()
    expect(toastPush).toHaveBeenCalledWith('Invalid document ID.', 'warning', 'Continue processing')
  })
})
