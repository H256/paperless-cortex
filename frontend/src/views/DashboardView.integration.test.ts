/* @vitest-environment jsdom */
import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref } from 'vue'

const summary = ref<Record<string, number> | null>({
  total: 200,
  reviewed: 50,
  unreviewed: 120,
  needs_review: 30,
  no_correspondent: 7,
  issue_date_is_import_date: 4,
})
const reviewLoading = ref(false)

vi.mock('../composables/useDashboardData', () => ({
  useDashboardData: () => ({
    loading: ref(false),
    error: ref(''),
    refresh: vi.fn(async () => undefined),
    data: ref({
      stats: {
        total: 200,
        processed: 200,
        unprocessed: 0,
        embeddings: 200,
        vision: 200,
        suggestions: 200,
        fully_processed: 200,
      },
      correspondents: [{ id: 1, name: 'ACME', count: 3 }],
      top_correspondents: [{ id: 1, name: 'ACME', count: 3 }],
      tags: [],
      top_tags: [],
      page_counts: [],
      document_types: [],
      unprocessed_by_correspondent: [],
      monthly_processing: [],
    }),
  }),
}))

vi.mock('../composables/useReviewSummary', () => ({
  useReviewSummary: () => ({
    loading: reviewLoading,
    error: ref(''),
    summary,
    refresh: vi.fn(async () => undefined),
  }),
}))

import DashboardView from './DashboardView.vue'

const mountView = () =>
  mount(DashboardView, {
    global: {
      stubs: {
        RouterLink: {
          props: ['to'],
          template: '<a :data-to="JSON.stringify(to)"><slot /></a>',
        },
      },
    },
  })

describe('DashboardView review progress', () => {
  it('shows the reviewed share and links the counters into the filtered list', () => {
    const wrapper = mountView()

    expect(wrapper.get('[data-testid="review-progress-headline"]').text()).toContain('25% reviewed')
    expect(wrapper.get('[data-testid="review-progress-headline"]').text()).toContain('50 / 200')

    const link = (key: string) =>
      JSON.parse(wrapper.get(`[data-testid="review-tile-${key}"]`).attributes('data-to') ?? '{}')
    expect(link('unreviewed').query).toEqual({ review_status: 'unreviewed' })
    expect(link('needs-review').query).toEqual({ review_status: 'needs_review' })
    expect(link('no-correspondent').query).toEqual({
      review_status: 'unreviewed',
      correspondent: '-1',
    })
    expect(link('import-date').query).toEqual({ review_status: 'unreviewed', import_date: '1' })
    expect(wrapper.get('[data-testid="review-tile-unreviewed"]').text()).toContain('120')
  })

  it('keeps the long correspondent list collapsed', () => {
    const wrapper = mountView()
    const details = wrapper.get('[data-testid="all-correspondents"]').element as HTMLDetailsElement
    expect(details.open).toBe(false)
  })

  it('does not break when the review summary is not available yet', () => {
    summary.value = null
    reviewLoading.value = true
    const wrapper = mountView()
    expect(wrapper.text()).toContain('Counting documents')
    summary.value = {
      total: 1,
      reviewed: 0,
      unreviewed: 1,
      needs_review: 0,
      no_correspondent: 0,
      issue_date_is_import_date: 0,
    }
    reviewLoading.value = false
  })
})
