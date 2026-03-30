// @vitest-environment jsdom
import { mount } from '@vue/test-utils'
import { computed, reactive, ref } from 'vue'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

let DocumentsView: unknown
const toastPush = vi.fn()

Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation(() => ({
    matches: false,
    media: '',
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})

const route = reactive({
  path: '/documents',
  fullPath: '/documents?page=3&view=cards',
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

const documents = ref([
  {
    id: 11,
    title: 'Doc 11',
    has_embeddings: true,
    has_suggestions: false,
    has_vision_pages: false,
  },
])

vi.mock('../composables/useDocumentsCatalog', () => ({
  useDocumentsCatalog: () => ({
    documents,
    page: ref(3),
    pageSize: ref(20),
    ordering: ref('-date'),
    totalCount: ref(25),
    tags: ref([]),
    correspondents: ref([]),
    selectedTag: ref(''),
    selectedCorrespondent: ref(''),
    selectedReviewStatus: ref('all'),
    dateFrom: ref(''),
    dateTo: ref(''),
    documentsLoading: ref(false),
    refetchDocuments: vi.fn(async () => undefined),
  }),
}))

vi.mock('../composables/useProcessingOverview', () => ({
  useProcessingOverview: () => ({
    syncStatus: ref({ status: 'idle', processed: 0, total: 0 }),
    embedStatus: ref({ status: 'idle', processed: 0, total: 0 }),
    stats: ref({
      total: 25,
      embeddings: 10,
      suggestions: 8,
      vision: 4,
      processed: 12,
      unprocessed: 13,
      fully_processed: 5,
    }),
    queueStatus: ref({ enabled: true, length: 2 }),
    lastSynced: ref('2026-03-12T22:00:00+00:00'),
    refresh: vi.fn(async () => undefined),
    clearQueueNow: vi.fn(async () => undefined),
    cancelSyncAndEmbeddings: vi.fn(async () => undefined),
  }),
}))

vi.mock('../composables/useProcessingMetrics', () => ({
  useProcessingMetrics: () => ({
    isProcessing: ref(false),
    hasQueuedWork: ref(true),
    showCancel: ref(true),
    embedLabel: ref('Embeddings'),
    progressPercent: ref(0),
    etaText: ref('--'),
    lastRunText: ref('just now'),
    processingProcessed: ref(0),
    processingTotal: ref(0),
    processingPercent: ref(0),
    processingEtaText: ref('--'),
  }),
}))

vi.mock('../composables/usePaperlessBaseUrl', () => ({
  usePaperlessBaseUrl: () => ({
    paperlessBaseUrl: ref('http://paperless.local'),
  }),
}))

vi.mock('../composables/useVisibleDocuments', () => ({
  useVisibleDocuments: () => ({
    visibleDocuments: computed(() => documents.value),
  }),
}))

vi.mock('../composables/useRunningTaskProgress', () => ({
  useRunningTaskProgress: () => ({
    runningByDocId: ref({ 11: { task: 'sync' } }),
  }),
}))

vi.mock('../composables/useDocumentsRouteState', () => ({
  useDocumentsRouteState: vi.fn(),
}))

vi.mock('../composables/useDocumentsTableControls', () => ({
  useDocumentsTableControls: () => ({
    toggleSort: vi.fn(),
    onPrevPage: vi.fn(),
    onNextPage: vi.fn(),
  }),
}))

describe('DocumentsView', () => {
  beforeAll(async () => {
    DocumentsView = (await import('./DocumentsView.vue')).default
  })

  afterEach(() => {
    documents.value = [
      {
        id: 11,
        title: 'Doc 11',
        has_embeddings: true,
        has_suggestions: false,
        has_vision_pages: false,
      },
    ]
    route.query = {}
    route.fullPath = '/documents?page=3&view=cards'
    vi.clearAllMocks()
  })

  it('wires header and table navigation actions through router pushes', async () => {
    const wrapper = mount(DocumentsView as never, {
      global: {
        stubs: {
          DocumentsHeaderSection: {
            template:
              '<div><button data-test="preview" @click="$emit(\'open-preview\')">preview</button><button data-test="queue" @click="$emit(\'open-queue\')">queue</button><button data-test="logs" @click="$emit(\'open-logs\')">logs</button></div>',
          },
          DocumentsFiltersPanel: true,
          DocumentsActiveFiltersStrip: true,
          DocumentsPresetBar: true,
          DocumentsQuickControls: true,
          DocumentsEmptyState: true,
          DocumentsTable: {
            template:
              '<div><button data-test="open-doc" @click="$emit(\'open-doc\', 11)">doc</button><button data-test="open-ops" @click="$emit(\'open-doc-operations\', 11)">ops</button><button data-test="open-suggestions" @click="$emit(\'open-doc-suggestions\', 11)">suggestions</button></div>',
          },
        },
      },
    })

    await wrapper.get('[data-test="preview"]').trigger('click')
    await wrapper.get('[data-test="queue"]').trigger('click')
    await wrapper.get('[data-test="logs"]').trigger('click')
    await wrapper.get('[data-test="open-doc"]').trigger('click')
    await wrapper.get('[data-test="open-ops"]').trigger('click')
    await wrapper.get('[data-test="open-suggestions"]').trigger('click')

    expect(router.push).toHaveBeenCalledWith('/processing/continue')
    expect(router.push).toHaveBeenCalledWith('/queue')
    expect(router.push).toHaveBeenCalledWith('/logs')
    expect(router.push).toHaveBeenCalledWith({
      path: '/documents/11',
      query: { return_to: encodeURIComponent('/documents?page=3&view=cards') },
    })
    expect(router.push).toHaveBeenCalledWith({
      path: '/documents/11',
      query: {
        return_to: encodeURIComponent('/documents?page=3&view=cards'),
        tab: 'operations',
      },
    })
    expect(router.push).toHaveBeenCalledWith({
      path: '/documents/11',
      query: {
        return_to: encodeURIComponent('/documents?page=3&view=cards'),
        tab: 'suggestions',
      },
    })
  })

  it('shows empty state when no visible documents remain and routes processing CTA', async () => {
    documents.value = []

    const wrapper = mount(DocumentsView as never, {
      global: {
        stubs: {
          DocumentsHeaderSection: true,
          DocumentsFiltersPanel: true,
          DocumentsActiveFiltersStrip: true,
          DocumentsPresetBar: true,
          DocumentsQuickControls: true,
          DocumentsEmptyState: {
            template:
              '<button data-test="empty-open-processing" @click="$emit(\'open-processing\')">open processing</button>',
          },
          DocumentsTable: true,
        },
      },
    })

    await wrapper.get('[data-test="empty-open-processing"]').trigger('click')

    expect(router.push).toHaveBeenCalledWith('/processing/continue')
  })

  it('blocks invalid document ids from the list view', async () => {
    const wrapper = mount(DocumentsView as never, {
      global: {
        stubs: {
          DocumentsHeaderSection: true,
          DocumentsFiltersPanel: true,
          DocumentsActiveFiltersStrip: true,
          DocumentsPresetBar: true,
          DocumentsQuickControls: true,
          DocumentsEmptyState: true,
          DocumentsTable: {
            template:
              '<div><button data-test="open-doc" @click="$emit(\'open-doc\', Number.NaN)">doc</button><button data-test="open-ops" @click="$emit(\'open-doc-operations\', Number.NaN)">ops</button><button data-test="open-suggestions" @click="$emit(\'open-doc-suggestions\', Number.NaN)">suggestions</button></div>',
          },
        },
      },
    })

    await wrapper.get('[data-test="open-doc"]').trigger('click')
    await wrapper.get('[data-test="open-ops"]').trigger('click')
    await wrapper.get('[data-test="open-suggestions"]').trigger('click')

    expect(router.push).not.toHaveBeenCalledWith(expect.objectContaining({ path: '/documents/NaN' }))
    expect(toastPush).toHaveBeenCalledTimes(3)
    expect(toastPush).toHaveBeenCalledWith('Invalid document ID.', 'warning', 'Documents')
  })
})
