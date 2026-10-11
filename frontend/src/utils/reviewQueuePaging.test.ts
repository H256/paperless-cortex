import { describe, expect, it, vi } from 'vitest'
import { createReviewQueueState } from './reviewQueue'
import {
  canExtendNext,
  canExtendPrev,
  extendReviewQueueNext,
  extendReviewQueuePrev,
  filterReviewRows,
  type FetchReviewPage,
} from './reviewQueuePaging'

const request = { page_size: 2, ordering: '-date', review_status: 'all' }

const pages = (data: Record<number, Array<Record<string, unknown>>>, count: number) =>
  vi.fn(async (params: { page: number }) => ({
    count,
    results: (data[params.page] ?? []) as never[],
  })) as unknown as FetchReviewPage & ReturnType<typeof vi.fn>

describe('extendReviewQueueNext (stable list)', () => {
  it('appends the following page and moves lastPage', async () => {
    const state = createReviewQueueState([1, 2], { request, lastPage: 1, totalPages: 3 })
    const fetchPage = pages({ 2: [{ id: 3 }, { id: 4, has_suggestions: true }] }, 6)

    const next = await extendReviewQueueNext(state, fetchPage)

    expect(next.ids).toEqual([1, 2, 3, 4])
    expect(next.lastPage).toBe(2)
    expect(next.suggestionIds).toEqual([4])
    expect(fetchPage).toHaveBeenCalledWith({ ...request, page: 2 })
  })

  it('marks the queue exhausted on the last page', async () => {
    const state = createReviewQueueState([1, 2], { request, lastPage: 2, totalPages: 2 })
    expect(canExtendNext(state)).toBe(false)
    const fetchPage = pages({}, 4)
    expect(await extendReviewQueueNext(state, fetchPage)).toBe(state)
    expect(fetchPage).not.toHaveBeenCalled()
  })

  it('does nothing without a list request', async () => {
    const state = createReviewQueueState([1, 2], { lastPage: 1, totalPages: 5 })
    expect(canExtendNext(state)).toBe(false)
  })
})

describe('extendReviewQueueNext (shrinking review list)', () => {
  it('rescans from page 1 and only appends documents that are not in the queue yet', async () => {
    // 1 and 2 were reviewed and left the list; 3 and 4 moved up to page 1.
    const state = createReviewQueueState([1, 2, 3, 4], {
      request: { ...request, review_status: 'unreviewed' },
      shrinking: true,
      lastPage: 1,
      totalPages: 3,
    })
    const fetchPage = pages({ 1: [{ id: 3 }, { id: 4 }], 2: [{ id: 5 }, { id: 6 }] }, 4)

    const next = await extendReviewQueueNext(state, fetchPage)

    expect(next.ids).toEqual([1, 2, 3, 4, 5, 6])
    expect(fetchPage).toHaveBeenNthCalledWith(1, expect.objectContaining({ page: 1 }))
    expect(fetchPage).toHaveBeenNthCalledWith(2, expect.objectContaining({ page: 2 }))
  })

  it('is exhausted when every row of the list is already queued', async () => {
    const state = createReviewQueueState([1, 2], {
      request: { ...request, review_status: 'unreviewed' },
      shrinking: true,
    })
    const fetchPage = pages({ 1: [{ id: 1 }, { id: 2 }] }, 2)

    const next = await extendReviewQueueNext(state, fetchPage)

    expect(next.ids).toEqual([1, 2])
    expect(next.exhaustedNext).toBe(true)
    expect(canExtendNext(next)).toBe(false)
  })
})

describe('extendReviewQueuePrev', () => {
  it('prepends the previous page for stable lists', async () => {
    const state = createReviewQueueState([5, 6], { request, firstPage: 3, lastPage: 3, totalPages: 3 })
    expect(canExtendPrev(state)).toBe(true)
    const fetchPage = pages({ 2: [{ id: 3 }, { id: 4 }] }, 6)

    const prev = await extendReviewQueuePrev(state, fetchPage)

    expect(prev.ids).toEqual([3, 4, 5, 6])
    expect(prev.firstPage).toBe(2)
  })

  it('never pages backwards for shrinking lists', () => {
    const state = createReviewQueueState([5], { request, firstPage: 3, shrinking: true })
    expect(canExtendPrev(state)).toBe(false)
  })
})

describe('filterReviewRows', () => {
  const rows = [
    { id: 1, has_embeddings: true, analysis_model: 'gpt-a' },
    { id: 2, analysis_model: 'other' },
  ]

  it('applies the analysis and model filters like the list does', () => {
    expect(filterReviewRows(rows, { analysis: 'analyzed', model: '' }).map((r) => r.id)).toEqual([1])
    expect(filterReviewRows(rows, { analysis: 'not_analyzed', model: '' }).map((r) => r.id)).toEqual(
      [2],
    )
    expect(filterReviewRows(rows, { analysis: 'all', model: 'GPT' }).map((r) => r.id)).toEqual([1])
  })
})
