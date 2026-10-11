// @vitest-environment jsdom
import { mount } from '@vue/test-utils'
import { nextTick, reactive, ref } from 'vue'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

let DocumentDetailView: unknown
const toastPush = vi.fn()
const detailLoading = ref(false)
const loadDocumentMock = vi.fn(async () => undefined)
const loadMetaMock = vi.fn(async () => undefined)
const loadPageTextsMock = vi.fn(async () => undefined)
const loadContentQualityMock = vi.fn(async () => undefined)
const loadOcrScoresMock = vi.fn(async () => undefined)
const loadSuggestionsMock = vi.fn(async () => undefined)
const refreshPipelineStatusMock = vi.fn(async () => undefined)
const refreshPipelineFanoutMock = vi.fn(async () => undefined)

const route = reactive({
  params: { id: '1' },
  query: { tab: 'operations' } as Record<string, string>,
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

vi.mock('../composables/usePaperlessBaseUrl', () => ({
  usePaperlessBaseUrl: () => ({
    paperlessBaseUrl: ref(''),
  }),
}))

vi.mock('../composables/useDocumentDetailData', () => ({
  useDocumentDetailData: () => ({
    document: ref({
      id: 1,
      title: 'Doc 1',
      modified: '2026-02-20T12:00:00+00:00',
      review_status: 'unreviewed',
      reviewed_at: null,
      local_overrides: false,
      notes: [],
      tags: [],
      created: '2026-02-20T12:00:00+00:00',
      correspondent: null,
      pending_tag_names: [],
      original_file_name: 'doc.pdf',
    }),
    loading: detailLoading,
    tags: ref([]),
    correspondents: ref([]),
    docTypes: ref([]),
    pageTexts: ref([]),
    pageTextsVisionProgress: ref(null),
    pageTextsError: ref(''),
    contentQuality: ref(null),
    contentQualityError: ref(''),
    ocrScores: ref([]),
    ocrScoresLoading: ref(false),
    ocrScoresError: ref(''),
    ocrComparison: ref({ agreement: null, recommendedSource: null, reason: null }),
    suggestions: ref({}),
    suggestionsLoading: ref(false),
    suggestionsError: ref(''),
    suggestionVariants: ref({}),
    suggestionVariantLoading: ref(false),
    suggestionVariantError: ref(''),
    loadDocument: loadDocumentMock,
    loadMeta: loadMetaMock,
    loadPageTexts: loadPageTextsMock,
    loadContentQuality: loadContentQualityMock,
    loadOcrScores: loadOcrScoresMock,
    loadSuggestions: loadSuggestionsMock,
    refreshSuggestions: vi.fn(async () => undefined),
    suggestField: vi.fn(async () => undefined),
    applyVariant: vi.fn(async () => undefined),
    applyToDocument: vi.fn(async () => undefined),
  }),
}))

vi.mock('../composables/useDocumentPipeline', () => ({
  useDocumentPipeline: () => ({
    pipelineStatus: ref(null),
    pipelineStatusLoading: ref(false),
    pipelineStatusError: ref(''),
    pipelineFanout: ref(null),
    pipelineFanoutLoading: ref(false),
    pipelineFanoutError: ref(''),
    refreshPipelineStatus: refreshPipelineStatusMock,
    refreshPipelineFanout: refreshPipelineFanoutMock,
    continuePipeline: vi.fn(async () => ({ enabled: true, enqueued: 0, missing_tasks: 0 })),
    continuePipelineLoading: ref(false),
  }),
}))

vi.mock('../composables/useDocumentOperations', () => ({
  useDocumentOperations: () => ({
    loading: ref(false),
    enqueueTask: vi.fn(async () => ({ enqueued: 0 })),
    cleanup: vi.fn(async () => ({ queued: false, updated: 0, processed: 0 })),
    resetAndReprocess: vi.fn(async () => ({ enqueued: 0 })),
  }),
}))

vi.mock('../composables/useDocumentTaskRuns', () => ({
  useDocumentTaskRuns: () => ({
    taskRuns: ref([]),
    taskRunsLoading: ref(false),
    taskRunsError: ref(''),
    refreshTaskRuns: vi.fn(async () => undefined),
  }),
}))

vi.mock('../composables/useDocumentReview', () => ({
  useDocumentReview: () => ({
    reviewMarking: ref(false),
    markReviewed: vi.fn(async () => ({ status: 'ok' })),
  }),
}))

vi.mock('../composables/useDocumentWriteback', () => ({
  useDocumentWriteback: () => ({
    writebackRunning: ref(false),
    writebackConfirmOpen: ref(false),
    writebackConflictOpen: ref(false),
    writebackConflicts: ref([]),
    writebackResolutions: ref({}),
    writebackErrorOpen: ref(false),
    writebackErrorMessage: ref(''),
    canWriteback: ref(true),
    writebackButtonTitle: ref('Write'),
    writebackButtonLabel: ref('Write'),
    openWritebackConfirm: vi.fn(),
    closeWritebackConfirm: vi.fn(),
    confirmWritebackNow: vi.fn(async () => undefined),
    cancelWritebackConflict: vi.fn(),
    applyWritebackConflictResolutions: vi.fn(async () => undefined),
    setConflictResolution: vi.fn(),
    closeWritebackError: vi.fn(),
  }),
}))

vi.mock('../composables/useDocumentProcessingState', () => ({
  fanoutStatusClass: vi.fn(() => ''),
  processingBadgeClass: vi.fn(() => ''),
  processingStateLabel: vi.fn(() => ''),
  useDocumentProcessingState: () => ({
    processingStatusItems: ref([]),
    processingRequiredCount: ref(0),
    processingDoneCount: ref(0),
    pipelineFanoutItems: ref([]),
    activeRun: ref(null),
    hasActiveTaskRuns: ref(false),
    activeRunLabel: ref(''),
    shouldAutoRefreshTimeline: ref(false),
    pipelinePreferredSource: ref('paperless_ocr'),
    isLargeDocumentMode: ref(false),
    largeDocumentHint: ref(''),
  }),
}))

vi.mock('../composables/useDocumentSimilarity', () => ({
  useDocumentSimilarity: () => ({
    similarMatches: ref([]),
    duplicateMatches: ref([]),
    loading: ref(false),
    error: ref(''),
    loadSimilarity: vi.fn(async () => undefined),
    reset: vi.fn(),
  }),
}))

vi.mock('../composables/useAutoRefresh', () => ({
  useAutoRefresh: vi.fn(),
}))

vi.mock('../components/PdfViewer.vue', () => ({
  default: {
    name: 'PdfViewer',
    emits: ['update:page'],
    props: {
      page: { type: Number, default: 1 },
      highlights: { type: Array, default: () => [] },
    },
    template:
      '<div data-test="pdf-viewer" :data-page="String(page)" :data-highlight-count="String((highlights || []).length)"><button data-test="pdf-next" @click="$emit(\'update:page\', 8)">next</button></div>',
  },
}))

describe('DocumentDetailView', () => {
  beforeAll(async () => {
    DocumentDetailView = (await import('./DocumentDetailView.vue')).default
  })

  afterEach(() => {
    route.params.id = '1'
    route.query = { tab: 'operations' }
    vi.clearAllMocks()
  })

  it('shows operations section when route query tab=operations', async () => {
    const wrapper = mount(DocumentDetailView as never, {
      global: {
        stubs: {
          IconButton: true,
          DocumentMetadataSection: true,
          DocumentTextQualitySection: true,
          DocumentSuggestionsSection: true,
          DocumentPagesSection: true,
          DocumentSimilarSection: true,
          DocumentChatSection: true,
          DocumentOperationsSection: { template: '<div data-test="ops-section" />' },
          WritebackConflictModal: true,
          ConfirmDialog: true,
        },
      },
    })

    await Promise.resolve()

    expect(wrapper.find('[data-test="ops-section"]').exists()).toBe(true)
    expect(wrapper.find('document-metadata-section-stub').exists()).toBe(false)
  })

  it('writes tab=operations to query and restores operations view from query', async () => {
    route.query = {}
    const wrapper = mount(DocumentDetailView as never, {
      global: {
        stubs: {
          IconButton: true,
          DocumentMetadataSection: { template: '<div data-test="meta-section" />' },
          DocumentTextQualitySection: true,
          DocumentSuggestionsSection: true,
          DocumentPagesSection: true,
          DocumentSimilarSection: true,
          DocumentChatSection: true,
          DocumentOperationsSection: { template: '<div data-test="ops-section" />' },
          WritebackConflictModal: true,
          ConfirmDialog: true,
        },
      },
    })

    await Promise.resolve()
    vi.clearAllMocks()

    expect(wrapper.find('[data-test="meta-section"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="ops-section"]').exists()).toBe(false)

    const operationsTab = wrapper.findAll('button').find((btn) => btn.text() === 'Operations')
    expect(operationsTab).toBeTruthy()
    await operationsTab!.trigger('click')
    await nextTick()
    await Promise.resolve()
    expect(router.replace).toHaveBeenCalledWith({ query: { tab: 'operations' } })
    expect(wrapper.find('[data-test="ops-section"]').exists()).toBe(true)

    route.query = { tab: 'operations' }
    await nextTick()
    await Promise.resolve()
    expect(wrapper.find('[data-test="ops-section"]').exists()).toBe(true)
  })

  it('does not load document APIs when route doc id is invalid', async () => {
    route.params.id = 'NaN'

    mount(DocumentDetailView as never, {
      global: {
        stubs: {
          IconButton: true,
          DocumentMetadataSection: true,
          DocumentTextQualitySection: true,
          DocumentSuggestionsSection: true,
          DocumentPagesSection: true,
          DocumentSimilarSection: true,
          DocumentChatSection: true,
          DocumentOperationsSection: true,
          WritebackConflictModal: true,
          ConfirmDialog: true,
        },
      },
    })

    await Promise.resolve()

    expect(loadDocumentMock).not.toHaveBeenCalled()
    expect(loadPageTextsMock).not.toHaveBeenCalled()
    expect(loadContentQualityMock).not.toHaveBeenCalled()
    expect(loadSuggestionsMock).not.toHaveBeenCalled()
    expect(refreshPipelineStatusMock).not.toHaveBeenCalled()
    expect(refreshPipelineFanoutMock).not.toHaveBeenCalled()
    expect(toastPush).toHaveBeenCalledWith('Invalid document ID.', 'warning', 'Document')
  })

  it('syncs pdf page/highlights from route query page+bbox', async () => {
    route.query = { tab: 'pages', page: '3', bbox: '1,2,3,4' }
    const wrapper = mount(DocumentDetailView as never, {
      global: {
        stubs: {
          IconButton: true,
          DocumentMetadataSection: true,
          DocumentTextQualitySection: true,
          DocumentSuggestionsSection: true,
          DocumentPagesSection: true,
          DocumentSimilarSection: true,
          DocumentChatSection: true,
          DocumentOperationsSection: true,
          WritebackConflictModal: true,
          ConfirmDialog: true,
        },
      },
    })

    await Promise.resolve()

    const pdf = wrapper.get('[data-test="pdf-viewer"]')
    expect(pdf.attributes('data-page')).toBe('3')
    expect(pdf.attributes('data-highlight-count')).toBe('1')
  })

  it('removes jump query key after consumption', async () => {
    route.query = { tab: 'pages', jump: 'token-1', keep: '1' }
    const wrapper = mount(DocumentDetailView as never, {
      global: {
        stubs: {
          IconButton: true,
          DocumentMetadataSection: true,
          DocumentTextQualitySection: true,
          DocumentSuggestionsSection: true,
          DocumentPagesSection: true,
          DocumentSimilarSection: true,
          DocumentChatSection: true,
          DocumentOperationsSection: true,
          WritebackConflictModal: true,
          ConfirmDialog: true,
        },
      },
    })

    await Promise.resolve()
    expect(router.replace).toHaveBeenCalledWith({ query: { tab: 'pages', keep: '1' } })
    expect(wrapper.find('[data-test="pdf-viewer"]').exists()).toBe(true)
  })

  it('updates page query and removes bbox when PdfViewer emits update:page', async () => {
    route.query = { tab: 'pages', page: '3', bbox: '1,2,3,4', keep: '1' }
    const wrapper = mount(DocumentDetailView as never, {
      global: {
        stubs: {
          IconButton: true,
          DocumentMetadataSection: true,
          DocumentTextQualitySection: true,
          DocumentSuggestionsSection: true,
          DocumentPagesSection: true,
          DocumentSimilarSection: true,
          DocumentChatSection: true,
          DocumentOperationsSection: true,
          WritebackConflictModal: true,
          ConfirmDialog: true,
        },
      },
    })

    await Promise.resolve()
    vi.clearAllMocks()
    await wrapper.get('[data-test="pdf-next"]').trigger('click')
    await nextTick()
    expect(router.replace).toHaveBeenCalledWith({ query: { tab: 'pages', page: '8', keep: '1' } })
  })

  it('removes tab query key when switching back to meta', async () => {
    route.query = { tab: 'operations', keep: '1' }
    const wrapper = mount(DocumentDetailView as never, {
      global: {
        stubs: {
          IconButton: true,
          DocumentMetadataSection: { template: '<div data-test="meta-section" />' },
          DocumentTextQualitySection: true,
          DocumentSuggestionsSection: true,
          DocumentPagesSection: true,
          DocumentSimilarSection: true,
          DocumentChatSection: true,
          DocumentOperationsSection: { template: '<div data-test="ops-section" />' },
          WritebackConflictModal: true,
          ConfirmDialog: true,
        },
      },
    })

    await Promise.resolve()
    vi.clearAllMocks()

    const metadataTab = wrapper.findAll('button').find((btn) => btn.text() === 'Metadata')
    expect(metadataTab).toBeTruthy()
    await metadataTab!.trigger('click')
    await nextTick()
    expect(router.replace).toHaveBeenCalledWith({ query: { keep: '1' } })
    expect(wrapper.find('[data-test="meta-section"]').exists()).toBe(true)
  })

  it('preserves unknown query keys across tab and page updates', async () => {
    route.query = { tab: 'pages', page: '3', bbox: '1,2,3,4', keep: '1', foo: 'bar' }
    const wrapper = mount(DocumentDetailView as never, {
      global: {
        stubs: {
          IconButton: true,
          DocumentMetadataSection: true,
          DocumentTextQualitySection: true,
          DocumentSuggestionsSection: true,
          DocumentPagesSection: true,
          DocumentSimilarSection: true,
          DocumentChatSection: true,
          DocumentOperationsSection: { template: '<div data-test="ops-section" />' },
          WritebackConflictModal: true,
          ConfirmDialog: true,
        },
      },
    })

    await Promise.resolve()
    vi.clearAllMocks()

    const operationsTab = wrapper.findAll('button').find((btn) => btn.text() === 'Operations')
    expect(operationsTab).toBeTruthy()
    await operationsTab!.trigger('click')
    await nextTick()
    expect(router.replace).toHaveBeenCalledWith({
      query: { tab: 'operations', page: '3', bbox: '1,2,3,4', keep: '1', foo: 'bar' },
    })

    vi.clearAllMocks()
    await wrapper.get('[data-test="pdf-next"]').trigger('click')
    await nextTick()
    expect(router.replace).toHaveBeenCalledWith({
      query: { tab: 'pages', page: '8', keep: '1', foo: 'bar' },
    })
  })

  it('shows the PDF next to the suggestions and lets the reviewer switch back to stacked', async () => {
    const store = new Map<string, string>()
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: {
        getItem: (key: string) => store.get(key) ?? null,
        setItem: (key: string, value: string) => void store.set(key, value),
        removeItem: (key: string) => void store.delete(key),
      },
    })
    route.query = { tab: 'suggestions' }
    const wrapper = mount(DocumentDetailView as never, {
      global: {
        stubs: {
          IconButton: true,
          DocumentMetadataSection: true,
          DocumentTextQualitySection: true,
          DocumentSuggestionsSection: { template: '<div data-test="suggestions-section" />' },
          DocumentPagesSection: true,
          DocumentSimilarSection: true,
          DocumentChatSection: true,
          DocumentOperationsSection: true,
          WritebackConflictModal: true,
          ConfirmDialog: true,
        },
      },
    })
    await nextTick()

    const layout = () => wrapper.get('[data-testid="detail-layout"]').classes().join(' ')
    expect(layout()).toContain('xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]')
    expect(wrapper.get('[data-testid="detail-pdf"]').classes().join(' ')).toContain('xl:sticky')

    await wrapper.get('[data-testid="split-view-toggle"]').setValue(false)
    expect(layout()).not.toContain('xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]')
    await nextTick()
    expect(store.get('document_detail_split_view')).toBe('0')
    wrapper.unmount()
  })

  it('keeps the stacked layout on other tabs', async () => {
    route.query = { tab: 'operations' }
    const wrapper = mount(DocumentDetailView as never, {
      global: {
        stubs: {
          IconButton: true,
          DocumentMetadataSection: true,
          DocumentTextQualitySection: true,
          DocumentSuggestionsSection: true,
          DocumentPagesSection: true,
          DocumentSimilarSection: true,
          DocumentChatSection: true,
          DocumentOperationsSection: true,
          WritebackConflictModal: true,
          ConfirmDialog: true,
        },
      },
    })
    await nextTick()

    expect(wrapper.get('[data-testid="detail-layout"]').classes().join(' ')).not.toContain(
      'xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]',
    )
    expect(wrapper.find('[data-testid="split-view-toggle"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('jumps the PDF to the page requested from the suggestions table', async () => {
    route.query = { tab: 'suggestions' }
    const wrapper = mount(DocumentDetailView as never, {
      global: {
        stubs: {
          IconButton: true,
          DocumentMetadataSection: true,
          DocumentTextQualitySection: true,
          DocumentSuggestionsSection: {
            emits: ['jumpToPage'],
            template: `<button data-test="jump" @click="$emit('jumpToPage', 3)">jump</button>`,
          },
          DocumentPagesSection: true,
          DocumentSimilarSection: true,
          DocumentChatSection: true,
          DocumentOperationsSection: true,
          WritebackConflictModal: true,
          ConfirmDialog: true,
        },
      },
    })
    await nextTick()

    await wrapper.get('[data-test="jump"]').trigger('click')
    await nextTick()

    expect(wrapper.get('[data-test="pdf-viewer"]').attributes('data-page')).toBe('3')
    wrapper.unmount()
  })

  it('keeps the suggestions mounted while the same document reloads, but not when switching', async () => {
    route.query = { tab: 'suggestions' }
    route.params.id = '1'
    const wrapper = mount(DocumentDetailView as never, {
      global: {
        stubs: {
          IconButton: true,
          DocumentMetadataSection: true,
          DocumentTextQualitySection: true,
          DocumentSuggestionsSection: { template: '<div data-test="suggestions-section" />' },
          DocumentPagesSection: true,
          DocumentSimilarSection: true,
          DocumentChatSection: true,
          DocumentOperationsSection: true,
          WritebackConflictModal: true,
          ConfirmDialog: true,
        },
      },
    })
    await nextTick()
    expect(wrapper.find('[data-test="suggestions-section"]').exists()).toBe(true)

    // same document (id 1) is reloading: the section must stay
    detailLoading.value = true
    await nextTick()
    expect(wrapper.find('[data-test="suggestions-section"]').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('Loading...')

    // another document is being loaded: placeholder instead of stale content
    route.params.id = '2'
    await nextTick()
    expect(wrapper.find('[data-test="suggestions-section"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('Loading...')

    detailLoading.value = false
    route.params.id = '1'
    wrapper.unmount()
  })
  it('confirms a single apply (preset) with a toast that says it is only local', async () => {
    route.query = { tab: 'suggestions' }
    const wrapper = mount(DocumentDetailView as never, {
      global: {
        stubs: {
          IconButton: true,
          DocumentMetadataSection: true,
          DocumentTextQualitySection: true,
          DocumentSuggestionsSection: {
            emits: ['applyToDocument'],
            template: `<button data-test="preset" @click="$emit('applyToDocument', 'preset', 'date', '2026-10-10')">p</button>`,
          },
          DocumentPagesSection: true,
          DocumentSimilarSection: true,
          DocumentChatSection: true,
          DocumentOperationsSection: true,
          WritebackConflictModal: true,
          ConfirmDialog: true,
        },
      },
    })
    await nextTick()
    toastPush.mockClear()

    await wrapper.get('[data-test="preset"]').trigger('click')
    await new Promise((resolve) => setTimeout(resolve, 0))

    const messages = toastPush.mock.calls.map((call) => String(call[0]))
    expect(messages.some((m) => m.includes('Applied issue date') && m.includes('Write back'))).toBe(true)
    wrapper.unmount()
  })
})
