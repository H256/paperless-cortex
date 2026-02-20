// @vitest-environment jsdom
import { mount } from '@vue/test-utils'
import { reactive, ref } from 'vue'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

let DocumentDetailView: unknown

const route = reactive({
  params: { id: '1' },
  query: { tab: 'operations' },
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
    push: vi.fn(),
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
    loading: ref(false),
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
    suggestions: ref({}),
    suggestionsLoading: ref(false),
    suggestionsError: ref(''),
    suggestionVariants: ref({}),
    suggestionVariantLoading: ref(false),
    suggestionVariantError: ref(''),
    loadDocument: vi.fn(async () => undefined),
    loadMeta: vi.fn(async () => undefined),
    loadPageTexts: vi.fn(async () => undefined),
    loadContentQuality: vi.fn(async () => undefined),
    loadOcrScores: vi.fn(async () => undefined),
    loadSuggestions: vi.fn(async () => undefined),
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
    refreshPipelineStatus: vi.fn(async () => undefined),
    refreshPipelineFanout: vi.fn(async () => undefined),
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

vi.mock('../composables/useAutoRefresh', () => ({
  useAutoRefresh: vi.fn(),
}))

vi.mock('../components/PdfViewer.vue', () => ({
  default: {
    name: 'PdfViewer',
    template: '<div data-test="pdf-viewer" />',
  },
}))

describe('DocumentDetailView', () => {
  beforeAll(async () => {
    DocumentDetailView = (await import('./DocumentDetailView.vue')).default
  })

  afterEach(() => {
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
          DocumentOperationsSection: { template: '<div data-test="ops-section" />' },
          WritebackConflictModal: true,
          ConfirmDialog: true,
          PdfViewer: true,
        },
      },
    })

    await Promise.resolve()

    expect(wrapper.find('[data-test="ops-section"]').exists()).toBe(true)
    expect(wrapper.find('document-metadata-section-stub').exists()).toBe(false)
  })
})
