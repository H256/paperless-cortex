// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { mount } from '@vue/test-utils'
import type { RouteLocationNormalizedLoaded, Router } from 'vue-router'
import { useReviewQueue } from './useReviewQueue'
import { createReviewQueueState, saveReviewQueue, saveReviewQueueState } from '../utils/reviewQueue'

const createLocalStorageMock = () => {
  const store = new Map<string, string>()
  return {
    getItem: (key: string) => (store.has(key) ? (store.get(key) as string) : null),
    setItem: (key: string, value: string) => void store.set(key, String(value)),
    removeItem: (key: string) => void store.delete(key),
    clear: () => store.clear(),
  }
}

const mountHarness = (
  docId: number,
  ids: number[],
  setup?: { state?: ReturnType<typeof createReviewQueueState>; options?: Parameters<typeof useReviewQueue>[3] },
) => {
  vi.stubGlobal('localStorage', createLocalStorageMock())
  if (setup?.state) saveReviewQueueState(setup.state)
  else saveReviewQueue(ids)
  const push = vi.fn(async () => undefined)
  const router = { push } as unknown as Router
  const route = {
    query: { return_to: '%2Fdocuments%3Fpage%3D2', tab: 'suggestions' },
  } as unknown as RouteLocationNormalizedLoaded
  const idRef = ref(docId)
  let api!: ReturnType<typeof useReviewQueue>
  const wrapper = mount(
    defineComponent({
      setup() {
        api = useReviewQueue(idRef, route, router, {
          prefetchDelayMs: 0,
          prefetchDocument: () => undefined,
          prefetchSuggestions: () => undefined,
          ...setup?.options,
        })
        return () => h('div')
      },
    }),
  )
  return { api, push, wrapper, idRef }
}

describe('useReviewQueue', () => {
  beforeEach(() => {
    vi.stubGlobal('localStorage', createLocalStorageMock())
  })

  it('navigates to the next and previous document and keeps return_to and tab', async () => {
    const { api, push } = mountHarness(20, [10, 20, 30])
    expect(api.hasQueue.value).toBe(true)
    expect(api.position.value?.index).toBe(1)

    await api.goNext()
    expect(push).toHaveBeenLastCalledWith({
      path: '/documents/30',
      query: { return_to: '%2Fdocuments%3Fpage%3D2', tab: 'suggestions' },
    })

    await api.goPrev()
    expect(push).toHaveBeenLastCalledWith({
      path: '/documents/10',
      query: { return_to: '%2Fdocuments%3Fpage%3D2', tab: 'suggestions' },
    })
  })

  it('has no queue for a document that is not part of the remembered list', () => {
    const { api } = mountHarness(99, [10, 20, 30])
    expect(api.hasQueue.value).toBe(false)
  })

  it('advances after review only when auto-advance is on and a next document exists', async () => {
    const { api, push } = mountHarness(10, [10, 20])
    expect(await api.advanceAfterReview()).toBe(true)
    expect(push).toHaveBeenCalledTimes(1)

    api.autoAdvance.value = false
    expect(await api.advanceAfterReview()).toBe(false)
    expect(push).toHaveBeenCalledTimes(1)
  })

  it('does not advance past the last document', async () => {
    const { api, push } = mountHarness(20, [10, 20])
    expect(await api.advanceAfterReview()).toBe(false)
    expect(push).not.toHaveBeenCalled()
  })

  it('reacts to j and k but ignores them while typing in an input', async () => {
    const { push, wrapper } = mountHarness(20, [10, 20, 30])
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'j' }))
    expect(push).toHaveBeenCalledTimes(1)

    const input = document.createElement('input')
    document.body.appendChild(input)
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', bubbles: true }))
    expect(push).toHaveBeenCalledTimes(1)

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k' }))
    expect(push).toHaveBeenCalledTimes(2)
    input.remove()
    wrapper.unmount()
  })

  it('loads the next page when moving past the last loaded document', async () => {
    const fetchPage = vi.fn(async () => ({ count: 4, results: [{ id: 30 }, { id: 40 }] }))
    const state = createReviewQueueState([10, 20], {
      request: { page_size: 2, ordering: '-date', review_status: 'all' },
      lastPage: 1,
      totalPages: 2,
    })
    const { api, push } = mountHarness(20, [], {
      state,
      options: { fetchPage: fetchPage as never, lookahead: 0 },
    })

    expect(api.hasNext.value).toBe(true)
    await api.goNext()

    expect(fetchPage).toHaveBeenCalledWith(expect.objectContaining({ page: 2 }))
    expect(push).toHaveBeenLastCalledWith(expect.objectContaining({ path: '/documents/30' }))
  })

  it('prefetches the next document and only requests suggestions that already exist', async () => {
    vi.useFakeTimers()
    const prefetchDocument = vi.fn()
    const prefetchSuggestions = vi.fn()
    const state = createReviewQueueState([10, 20, 30], { suggestionIds: [30] })
    mountHarness(20, [], {
      state,
      options: { prefetchDelayMs: 100, prefetchDocument, prefetchSuggestions },
    })

    await vi.advanceTimersByTimeAsync(150)

    expect(prefetchDocument).toHaveBeenCalledWith(30)
    expect(prefetchSuggestions).toHaveBeenCalledWith(30)
    vi.useRealTimers()
  })

  it('does not request suggestions for documents without them', async () => {
    vi.useFakeTimers()
    const prefetchDocument = vi.fn()
    const prefetchSuggestions = vi.fn()
    const state = createReviewQueueState([10, 20, 30])
    mountHarness(20, [], {
      state,
      options: { prefetchDelayMs: 100, prefetchDocument, prefetchSuggestions },
    })

    await vi.advanceTimersByTimeAsync(150)

    expect(prefetchDocument).toHaveBeenCalledWith(30)
    expect(prefetchSuggestions).not.toHaveBeenCalled()
    vi.useRealTimers()
  })
})
