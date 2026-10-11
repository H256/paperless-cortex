import type { ReviewClientFilter, ReviewListRequest, ReviewQueueState } from './reviewQueue'

export type ReviewPageRow = {
  id?: number | null
  has_embeddings?: boolean | null
  has_suggestions?: boolean | null
  has_vision_pages?: boolean | null
  analysis_model?: string | null
}

export type ReviewPageResponse = {
  count?: number | null
  results?: ReviewPageRow[] | null
}

export type FetchReviewPage = (
  params: ReviewListRequest & { page: number },
) => Promise<ReviewPageResponse>

/** Same client-side filtering as the documents list (analysis state and model). */
export const filterReviewRows = (
  rows: ReviewPageRow[],
  filter: ReviewClientFilter,
): ReviewPageRow[] => {
  let out = rows
  if (filter.analysis !== 'all') {
    const wantAnalyzed = filter.analysis === 'analyzed'
    out = out.filter(
      (row) =>
        Boolean(row.has_embeddings || row.has_suggestions || row.has_vision_pages) === wantAnalyzed,
    )
  }
  const needle = filter.model.trim().toLowerCase()
  if (needle) {
    out = out.filter((row) =>
      String(row.analysis_model || '')
        .toLowerCase()
        .includes(needle),
    )
  }
  return out
}

const MAX_SCAN_PAGES = 10

const totalPagesOf = (response: ReviewPageResponse, pageSize: number) =>
  Math.max(1, Math.ceil(Number(response.count ?? 0) / Math.max(1, pageSize)))

const suggestionIdsOf = (rows: ReviewPageRow[]) =>
  rows
    .filter((row) => row.has_suggestions && Number.isInteger(Number(row.id)))
    .map((row) => Number(row.id))

const freshIds = (rows: ReviewPageRow[], seen: Set<number>) => {
  const out: number[] = []
  for (const row of rows) {
    const id = Number(row.id)
    if (!Number.isInteger(id) || id <= 0 || seen.has(id)) continue
    seen.add(id)
    out.push(id)
  }
  return out
}

export const canExtendNext = (state: ReviewQueueState) =>
  Boolean(state.request) &&
  !state.exhaustedNext &&
  (state.shrinking || state.lastPage < state.totalPages)

export const canExtendPrev = (state: ReviewQueueState) =>
  Boolean(state.request) && !state.shrinking && state.firstPage > 1

/**
 * Append documents that follow the loaded ones.
 *
 * Stable lists continue with `lastPage + 1`. Review filters shrink while documents
 * are reviewed (a plain `page + 1` would skip rows that moved up), so those lists are
 * re-scanned from page 1 and only documents that are not in the queue yet are appended.
 * Returns the unchanged state when nothing was added.
 */
export const extendReviewQueueNext = async (
  state: ReviewQueueState,
  fetchPage: FetchReviewPage,
): Promise<ReviewQueueState> => {
  const request = state.request
  if (!request || !canExtendNext(state)) return state
  const seen = new Set(state.ids)
  let page = state.shrinking ? 1 : state.lastPage + 1
  let totalPages = state.totalPages

  for (let scanned = 0; scanned < MAX_SCAN_PAGES; scanned += 1) {
    const response = await fetchPage({ ...request, page })
    totalPages = totalPagesOf(response, request.page_size)
    const rows = filterReviewRows(response.results ?? [], state.clientFilter)
    const added = freshIds(rows, seen)
    if (added.length) {
      return {
        ...state,
        ids: [...state.ids, ...added],
        suggestionIds: [...state.suggestionIds, ...suggestionIdsOf(rows)],
        lastPage: state.shrinking ? state.lastPage : page,
        totalPages,
      }
    }
    if (page >= totalPages) {
      return { ...state, totalPages, exhaustedNext: true }
    }
    page += 1
  }
  return state
}

/** Prepend the previous page (stable lists only). */
export const extendReviewQueuePrev = async (
  state: ReviewQueueState,
  fetchPage: FetchReviewPage,
): Promise<ReviewQueueState> => {
  const request = state.request
  if (!request || !canExtendPrev(state)) return state
  const seen = new Set(state.ids)
  const page = state.firstPage - 1
  const response = await fetchPage({ ...request, page })
  const rows = filterReviewRows(response.results ?? [], state.clientFilter)
  const added = freshIds(rows, seen)
  return {
    ...state,
    ids: [...added, ...state.ids],
    suggestionIds: [...state.suggestionIds, ...suggestionIdsOf(rows)],
    firstPage: page,
    totalPages: totalPagesOf(response, request.page_size),
  }
}
