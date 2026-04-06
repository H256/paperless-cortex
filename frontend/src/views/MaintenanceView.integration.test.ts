/* @vitest-environment jsdom */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref } from 'vue'

const toastPush = vi.fn()
const loadWorkerLockStatus = vi.fn(async () => null)

vi.mock('../stores/toastStore', () => ({
  useToastStore: () => ({
    push: toastPush,
  }),
}))

vi.mock('../composables/useMaintenanceOps', () => ({
  useMaintenanceOps: () => ({
    syncStatus: ref({ status: 'idle', processed: 0, total: 0, started_at: null, eta_seconds: null }),
    embedStatus: ref({ status: 'idle', processed: 0, total: 0, started_at: null, eta_seconds: null }),
    workerLockStatus: ref({ has_lock: false, owner: null, ttl_seconds: null }),
    workerLockLoading: ref(false),
    reprocessRunning: ref(false),
    visionLoading: ref(false),
    suggestionsLoading: ref(false),
    embeddingsLoading: ref(false),
    similarityIndexLoading: ref(false),
    missingVectorChunksLoading: ref(false),
    clearAllLoading: ref(false),
    cleanupLoading: ref(false),
    correspondentsSyncLoading: ref(false),
    tagsSyncLoading: ref(false),
    workerLockResetLoading: ref(false),
    loadWorkerLockStatus,
    reprocessAll: vi.fn(async () => ({})),
    removeVisionOcr: vi.fn(async () => ({ deleted: 0 })),
    removeSuggestions: vi.fn(async () => ({ deleted: 0 })),
    removeEmbeddings: vi.fn(async () => ({ deleted: 0, qdrant_deleted: 0, qdrant_errors: 0 })),
    removeSimilarityIndex: vi.fn(async () => ({ deleted: 0, qdrant_deleted: 0, qdrant_errors: 0 })),
    findMissingVectorChunks: vi.fn(async () => ({
      provider: 'weaviate',
      scanned_docs: 0,
      affected_docs: 0,
      fully_missing_docs: 0,
      partial_missing_docs: 0,
      limit: 100,
      truncated: false,
      items: [],
    })),
    clearAllIntelligence: vi.fn(async () => ({})),
    cleanupTexts: vi.fn(async () => ({ queued: true, docs: 0, enqueued: 0, processed: 0, updated: 0 })),
    syncCorrespondentsNow: vi.fn(async () => ({ count: 0, upserted: 0 })),
    syncTagsNow: vi.fn(async () => ({ count: 0, upserted: 0 })),
    resetWorkerLockNow: vi.fn(async () => ({ had_lock: false, reset: false, reason: 'none' })),
  }),
}))

import MaintenanceView from './MaintenanceView.vue'

describe('MaintenanceView runtime rows', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders worker lock maintenance controls without runtime config rows', async () => {
    const wrapper = mount(MaintenanceView)
    await Promise.resolve()

    expect(wrapper.text()).toContain('Worker lock')
    expect(wrapper.text()).not.toContain('Runtime Configuration')
    expect(loadWorkerLockStatus).toHaveBeenCalled()
    expect(toastPush).not.toHaveBeenCalled()
  })
})
