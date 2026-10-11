// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { mount } from '@vue/test-utils'
import type { RouteLocationNormalizedLoaded, Router } from 'vue-router'
import { useReviewQueue } from './useReviewQueue'
import { saveReviewQueue } from '../utils/reviewQueue'

const createLocalStorageMock = () => {
  const store = new Map<string, string>()
  return {
    getItem: (key: string) => (store.has(key) ? (store.get(key) as string) : null),
    setItem: (key: string, value: string) => void store.set(key, String(value)),
    removeItem: (key: string) => void store.delete(key),
    clear: () => store.clear(),
  }
}

const mountHarness = (docId: number, ids: number[]) => {
  vi.stubGlobal('localStorage', createLocalStorageMock())
  saveReviewQueue(ids)
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
        api = useReviewQueue(idRef, route, router)
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
})
