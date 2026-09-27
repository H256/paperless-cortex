/* @vitest-environment jsdom */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'

const listDocumentsMock = vi.fn()
const getTagsMock = vi.fn(async (..._args: unknown[]) => ({ results: [] }))
const getCorrespondentsMock = vi.fn(async (..._args: unknown[]) => ({ results: [] }))

vi.mock('../services/documents', () => ({
  listDocuments: (...args: unknown[]) => listDocumentsMock(...args),
  getTags: (...args: unknown[]) => getTagsMock(...args),
  getCorrespondents: (...args: unknown[]) => getCorrespondentsMock(...args),
}))

import { useDocumentsCatalog } from './useDocumentsCatalog'
import type { DocumentRow } from '../services/documents'

const retryDisabledQueryClient = () =>
  new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })

const mountCatalog = (queryClient: QueryClient) => {
  const TestHost = defineComponent({
    setup() {
      const catalog = useDocumentsCatalog()
      return { catalog }
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
  return (wrapper.vm as unknown as { catalog: ReturnType<typeof useDocumentsCatalog> }).catalog
}

describe('useDocumentsCatalog', () => {
  beforeEach(() => {
    listDocumentsMock.mockReset()
    getTagsMock.mockClear()
    getCorrespondentsMock.mockClear()
  })

  it('flips the error state when the initial documents list request fails', async () => {
    listDocumentsMock.mockRejectedValue(new Error('backend unreachable'))

    const catalog = mountCatalog(retryDisabledQueryClient())

    await vi.waitFor(() => expect(catalog.documentsError.value).toBe(true))

    expect(listDocumentsMock).toHaveBeenCalledTimes(1)
    expect(catalog.documents.value).toEqual([])
    expect(catalog.documentsLoading.value).toBe(false)
  })

  it('clears the error state and reloads data when the retry succeeds', async () => {
    const row = {
      id: 7,
      title: 'Doc 7',
      has_embeddings: false,
      has_suggestions: false,
      has_vision_pages: false,
    } as DocumentRow
    listDocumentsMock
      .mockRejectedValueOnce(new Error('backend unreachable'))
      .mockResolvedValueOnce({ results: [row], count: 1 })

    const catalog = mountCatalog(retryDisabledQueryClient())

    await vi.waitFor(() => expect(catalog.documentsError.value).toBe(true))

    await catalog.refetchDocuments()

    expect(listDocumentsMock).toHaveBeenCalledTimes(2)
    expect(catalog.documentsError.value).toBe(false)
    expect(catalog.documents.value).toEqual([row])
    expect(catalog.totalCount.value).toBe(1)
  })
})
