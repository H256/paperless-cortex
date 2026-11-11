// @vitest-environment jsdom
import { mount } from '@vue/test-utils'
import { computed, onMounted, reactive, ref } from 'vue'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

let DocumentsView: unknown
const toastPush = vi.fn()
const refetchDocumentsMock = vi.fn(async () => undefined)

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
const documentsError = ref(false)
// Expose the catalog refs so tests can assert the restored filter state.
const catalogRefs = {
  selectedReviewStatus: ref<'all' | 'unreviewed' | 'reviewed' | 'needs_review'>('all'),
  analysisFilter: ref<'all' | 'analyzed' | 'not_analyzed'>('all'),
  selectedCorrespondent: ref(''),
  issueDateIsImportDate: ref(false),
  searchQuery: ref(''),
  page: ref(1),
}

vi.mock('../composables/useDocumentsCatalog', () => ({
  useDocumentsCatalog: () => ({
    documents,
    page: catalogRefs.page,
    pageSize: ref(20),
    ordering: ref('-date'),
    totalCount: ref(25),
    listRequest: ref({ page_size: 20, ordering: '-date', review_status: 'all' }),
    issueDateIsImportDate: catalogRefs.issueDateIsImportDate,
    tags: ref([]),
    correspondents: ref([]),
    selectedTag: ref(''),
    selectedCorrespondent: catalogRefs.selectedCorrespondent,
    selectedReviewStatus: catalogRefs.selectedReviewStatus,
    dateFrom: ref(''),
    dateTo: ref(''),
    searchQuery: catalogRefs.searchQuery,
    documentsLoading: ref(false),
    documentsError,
    refetchDocuments: refetchDocumentsMock,
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

vi.mock('../composables/useReviewSummary', () => ({
  useReviewSummary: () => ({
    loading: ref(false),
    error: ref(''),
    summary: ref({
      total: 10,
      reviewed: 4,
      unreviewed: 5,
      needs_review: 1,
      no_correspondent: 2,
      issue_date_is_import_date: 3,
    }),
    refresh: vi.fn(async () => undefined),
  }),
}))

vi.mock('../composables/useRunningTaskProgress', () => ({
  useRunningTaskProgress: () => ({
    runningByDocId: ref({ 11: { task: 'sync' } }),
  }),
}))

vi.mock('../composables/useDocumentsRouteState', () => ({
  useDocumentsRouteState: (refs: {
    [key: string]: { value: unknown }
  } & { selectedReviewStatus: { value: string } }) => {
    // Mimic the real composable: apply the URL query to the refs on mount so
    // tests can assert how an explicit URL filter interacts with the restore.
    onMounted(() => {
      const reviewStatus = route.query.review_status
      if (reviewStatus === 'reviewed' || reviewStatus === 'unreviewed' || reviewStatus === 'needs_review') {
        refs.selectedReviewStatus.value = reviewStatus
      }
    })
  },
}))

const readLastPresetMock = vi.fn(() => '')
const writeLastPresetMock = vi.fn()
const clearLastPresetMock = vi.fn()
vi.mock('../utils/documentsPresetStorage', () => ({
  readLastPreset: () => readLastPresetMock(),
  writeLastPreset: (key: string) => writeLastPresetMock(key),
  clearLastPreset: () => clearLastPresetMock(),
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
    documentsError.value = false
    catalogRefs.page.value = 1
    catalogRefs.selectedReviewStatus.value = 'all'
    catalogRefs.analysisFilter.value = 'all'
    catalogRefs.selectedCorrespondent.value = ''
    catalogRefs.issueDateIsImportDate.value = false
    catalogRefs.searchQuery.value = ''
    vi.clearAllMocks()
  })

  it('wires header and table navigation actions through router pushes', async () => {
    catalogRefs.page.value = 3
    const wrapper = mount(DocumentsView as never, {
      global: {
        stubs: {
          DocumentsHeaderSection: {
            template:
              '<div><button data-test="preview" @click="$emit(\'open-preview\')">preview</button><button data-test="queue" @click="$emit(\'open-queue\')">queue</button><button data-test="logs" @click="$emit(\'open-logs\')">logs</button></div>',
          },
          DocumentsFiltersPanel: true,
          DocumentsActiveFiltersStrip: true,
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
          DocumentsQuickControls: true,
          DocumentsTable: true,
        },
      },
    })

    expect(wrapper.text()).toContain('No documents available yet')

    const cta = wrapper.findAll('button').find((b) => b.text() === 'Continue processing')
    if (!cta) {
      throw new Error('Expected Continue processing button')
    }
    await cta.trigger('click')

    expect(router.push).toHaveBeenCalledWith('/processing/continue')
  })

  it('shows the error state with a retry button when the documents query fails without data', async () => {
    documents.value = []
    documentsError.value = true

    const wrapper = mount(DocumentsView as never, {
      global: {
        stubs: {
          DocumentsHeaderSection: true,
          DocumentsFiltersPanel: true,
          DocumentsActiveFiltersStrip: true,
          DocumentsQuickControls: true,
          DocumentsTable: true,
        },
      },
    })

    expect(wrapper.text()).toContain("Couldn't load documents")
    expect(wrapper.text()).not.toContain('No documents available yet')
    expect(wrapper.text()).not.toContain('Clear filters')
    expect(wrapper.text()).not.toContain('Continue processing')

    const retryButton = wrapper.findAll('button').find((b) => b.text() === 'Retry')
    if (!retryButton) {
      throw new Error('Expected Retry button')
    }
    await retryButton.trigger('click')

    expect(refetchDocumentsMock).toHaveBeenCalledTimes(1)
  })

  it('blocks invalid document ids from the list view', async () => {
    const wrapper = mount(DocumentsView as never, {
      global: {
        stubs: {
          DocumentsHeaderSection: true,
          DocumentsFiltersPanel: true,
          DocumentsActiveFiltersStrip: true,
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

  it('restores the last applied preset on mount when the URL has no explicit filter', async () => {
    readLastPresetMock.mockReturnValue('unreviewed')
    const wrapper = mount(DocumentsView as never, {
      global: {
        stubs: {
          DocumentsHeaderSection: true,
          DocumentsFiltersPanel: true,
          DocumentsActiveFiltersStrip: true,
          DocumentsPresetBar: true,
          DocumentsQuickControls: true,
          DocumentsEmptyState: true,
          DocumentsTable: true,
        },
      },
    })
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(catalogRefs.selectedReviewStatus.value).toBe('unreviewed')
    expect(catalogRefs.page.value).toBe(1)
    wrapper.unmount()
  })

  it('does not restore the preset when the URL already carries an explicit filter', async () => {
    route.query = { review_status: 'reviewed' }
    readLastPresetMock.mockReturnValue('unreviewed')
    const wrapper = mount(DocumentsView as never, {
      global: {
        stubs: {
          DocumentsHeaderSection: true,
          DocumentsFiltersPanel: true,
          DocumentsActiveFiltersStrip: true,
          DocumentsPresetBar: true,
          DocumentsQuickControls: true,
          DocumentsEmptyState: true,
          DocumentsTable: true,
        },
      },
    })
    await new Promise((resolve) => setTimeout(resolve, 0))

    // The explicit URL filter wins; the remembered preset is not applied.
    expect(catalogRefs.selectedReviewStatus.value).toBe('reviewed')
    wrapper.unmount()
  })

  it('clears the remembered preset when all filters are cleared', async () => {
    const wrapper = mount(DocumentsView as never, {
      global: {
        stubs: {
          DocumentsHeaderSection: true,
          DocumentsFiltersPanel: true,
          DocumentsActiveFiltersStrip: true,
          DocumentsPresetBar: true,
          DocumentsQuickControls: {
            template:
              '<div><button data-test="clear-all" @click="clearAll">clear</button></div>',
            methods: {
              clearAll() {
                this.$emit('clear-all-filters')
              },
            },
          },
          DocumentsEmptyState: true,
          DocumentsTable: true,
        },
      },
    })
    await new Promise((resolve) => setTimeout(resolve, 0))

    await wrapper.get('[data-test="clear-all"]').trigger('click')
    expect(clearLastPresetMock).toHaveBeenCalled()
    wrapper.unmount()
  })
})
