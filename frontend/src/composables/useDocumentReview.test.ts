/* @vitest-environment jsdom */
import { describe, expect, it, vi } from 'vitest'
import { defineComponent, h, nextTick, ref } from 'vue'
import { mount } from '@vue/test-utils'
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'

const markDocumentReviewedMock = vi.fn()

vi.mock('../services/documents', () => ({
  markDocumentReviewed: (...args: unknown[]) => markDocumentReviewedMock(...args),
}))

import { useDocumentReview } from './useDocumentReview'

describe('useDocumentReview', () => {
  it('marks reviewed and invalidates dependent queries', async () => {
    markDocumentReviewedMock.mockResolvedValue({ status: 'ok', doc_id: 5 })
    const invalidateQueries = vi.fn(async () => undefined)
    const queryClient = new QueryClient()
    queryClient.invalidateQueries = invalidateQueries as typeof queryClient.invalidateQueries

    const TestHost = defineComponent({
      setup() {
        const docId = ref(5)
        const review = useDocumentReview(docId)
        return { review }
      },
      render() {
        return h('div')
      },
    })

    const wrapper = mount(TestHost, {
      global: {
        plugins: [[VueQueryPlugin, { queryClient }]],
      },
    })

    const result = await (wrapper.vm as unknown as { review: ReturnType<typeof useDocumentReview> }).review.markReviewed()
    expect(result.status).toBe('ok')
    expect(markDocumentReviewedMock).toHaveBeenCalledWith(5)
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ['documents-list'] })
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ['dashboard-data'] })
  })

  it('exposes pending state while mutation is running and propagates errors', async () => {
    let resolveFn: (value: { status: string; doc_id: number }) => void = () => undefined
    markDocumentReviewedMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveFn = resolve
        }),
    )
    const queryClient = new QueryClient()

    const TestHost = defineComponent({
      setup() {
        const docId = ref(8)
        const review = useDocumentReview(docId)
        return { review }
      },
      render() {
        return h('div')
      },
    })

    const wrapper = mount(TestHost, {
      global: {
        plugins: [[VueQueryPlugin, { queryClient }]],
      },
    })
    const review = (wrapper.vm as unknown as { review: ReturnType<typeof useDocumentReview> }).review

    const pendingPromise = review.markReviewed()
    await nextTick()
    expect(review.reviewMarking.value).toBe(true)
    resolveFn({ status: 'ok', doc_id: 8 })
    await pendingPromise
    expect(review.reviewMarking.value).toBe(false)

    const expectedError = new Error('mark failed')
    markDocumentReviewedMock.mockRejectedValueOnce(expectedError)
    await expect(review.markReviewed()).rejects.toThrow('mark failed')
  })
})
