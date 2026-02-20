/* @vitest-environment jsdom */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref } from 'vue'

const toastPush = vi.fn()
const refreshRuntime = vi.fn(async () => null)
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
    runtime: ref({
      paperless_base_url: 'http://paperless.local',
      llm_base_url: 'http://llm.local',
      qdrant_url: 'http://qdrant.local',
      redis_host: 'redis.local',
      text_model: 'gpt-test',
      embedding_model: 'embed-test',
      vision_model: 'vision-test',
      evidence_max_pages: 3,
      evidence_min_snippet_chars: 20,
    }),
    workerLockStatus: ref({ has_lock: false, owner: null, ttl_seconds: null }),
    workerLockLoading: ref(false),
    reprocessRunning: ref(false),
    visionLoading: ref(false),
    suggestionsLoading: ref(false),
    embeddingsLoading: ref(false),
    clearAllLoading: ref(false),
    cleanupLoading: ref(false),
    correspondentsSyncLoading: ref(false),
    tagsSyncLoading: ref(false),
    workerLockResetLoading: ref(false),
    loadWorkerLockStatus,
    refreshRuntime,
    reprocessAll: vi.fn(async () => ({})),
    removeVisionOcr: vi.fn(async () => ({ deleted: 0 })),
    removeSuggestions: vi.fn(async () => ({ deleted: 0 })),
    removeEmbeddings: vi.fn(async () => ({ deleted: 0, qdrant_deleted: 0, qdrant_errors: 0 })),
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
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: vi.fn(async () => undefined) },
      configurable: true,
    })
  })

  it('copies runtime values from row action buttons', async () => {
    const wrapper = mount(MaintenanceView)
    await Promise.resolve()

    const copyButtons = wrapper.findAll('button').filter((b) => b.text() === 'Copy')
    expect(copyButtons.length).toBeGreaterThan(0)
    const firstCopyButton = copyButtons[0]
    if (!firstCopyButton) throw new Error('Expected at least one copy button')
    await firstCopyButton.trigger('click')

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('http://paperless.local')
    expect(toastPush).toHaveBeenCalled()
    expect(wrapper.text()).toContain('Copied')
  })
})
