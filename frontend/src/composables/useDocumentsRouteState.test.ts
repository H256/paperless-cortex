// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, nextTick, reactive, ref } from 'vue'

const route = reactive({ path: '/documents', query: {} as Record<string, string> })
const replace = vi.fn(async (target: { query: Record<string, string> }) => {
  route.query = target.query
})

vi.mock('vue-router', () => ({
  useRoute: () => route,
  useRouter: () => ({ replace }),
}))

import { readStoredDocumentsQuery, useDocumentsRouteState } from './useDocumentsRouteState'

const store = new Map<string, string>()

const mountWithRefs = () => {
  const refs = {
    page: ref(1),
    pageSize: ref(20),
    ordering: ref('-date'),
    selectedTag: ref(''),
    selectedCorrespondent: ref(''),
    selectedReviewStatus: ref<'all' | 'unreviewed' | 'reviewed' | 'needs_review'>('all'),
    dateFrom: ref(''),
    dateTo: ref(''),
    analysisFilter: ref<'all' | 'analyzed' | 'not_analyzed'>('all'),
    modelFilter: ref(''),
    searchQuery: ref(''),
    runningOnly: ref(false),
    issueDateIsImportDate: ref(false),
  }
  const wrapper = mount(
    defineComponent({
      setup() {
        useDocumentsRouteState(refs)
        return () => null
      },
    }),
  )
  return { refs, wrapper }
}

describe('useDocumentsRouteState last filter', () => {
  beforeEach(() => {
    store.clear()
    route.query = {}
    replace.mockClear()
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: {
        getItem: (key: string) => store.get(key) ?? null,
        setItem: (key: string, value: string) => void store.set(key, value),
        removeItem: (key: string) => void store.delete(key),
      },
    })
  })

  it('restores the last used filters when the list is opened without a query', async () => {
    store.set(
      'documents_last_query',
      JSON.stringify({ review_status: 'unreviewed', correspondent: '-1', page: '4' }),
    )

    const { refs, wrapper } = mountWithRefs()
    await nextTick()

    expect(refs.selectedReviewStatus.value).toBe('unreviewed')
    expect(refs.selectedCorrespondent.value).toBe('-1')
    expect(refs.page.value).toBe(1)
    wrapper.unmount()
  })

  it('prefers the filters of the URL over the stored ones', async () => {
    store.set('documents_last_query', JSON.stringify({ review_status: 'unreviewed' }))
    route.query = { review_status: 'reviewed' }

    const { refs, wrapper } = mountWithRefs()
    await nextTick()

    expect(refs.selectedReviewStatus.value).toBe('reviewed')
    wrapper.unmount()
  })

  it('stores filter changes and forgets them again when everything is cleared', async () => {
    const { refs, wrapper } = mountWithRefs()
    await nextTick()

    refs.selectedReviewStatus.value = 'needs_review'
    await nextTick()
    await nextTick()
    expect(readStoredDocumentsQuery()).toEqual({ review_status: 'needs_review' })

    refs.selectedReviewStatus.value = 'all'
    await nextTick()
    await nextTick()
    expect(readStoredDocumentsQuery()).toBeNull()
    wrapper.unmount()
  })

  it('ignores a broken stored value', async () => {
    store.set('documents_last_query', '{not json')
    const { refs, wrapper } = mountWithRefs()
    await nextTick()
    expect(refs.selectedReviewStatus.value).toBe('all')
    wrapper.unmount()
  })
})
