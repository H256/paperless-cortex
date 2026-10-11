const QUEUE_KEY = 'review_queue_v2'
const LEGACY_QUEUE_KEY = 'review_queue_v1'
const AUTO_ADVANCE_KEY = 'review_auto_advance'

export type ReviewListRequest = {
  page_size: number
  ordering?: string | null
  correspondent__id?: number | null
  tags__id?: number | null
  document_date__gte?: string | null
  document_date__lte?: string | null
  q?: string | null
  include_derived?: boolean
  include_summary_preview?: boolean
  review_status?: string
}

export type ReviewClientFilter = {
  analysis: 'all' | 'analyzed' | 'not_analyzed'
  model: string
}

export type ReviewQueueState = {
  ids: number[]
  firstPage: number
  lastPage: number
  totalPages: number
  /** The server list shrinks while documents are reviewed (review filters). */
  shrinking: boolean
  /** Request used to load the list; null disables paging beyond the stored ids. */
  request: ReviewListRequest | null
  clientFilter: ReviewClientFilter
  /** No further documents were found after the last loaded one. */
  exhaustedNext: boolean
  /** Ids whose list row already had suggestions (safe to prefetch without generating). */
  suggestionIds: number[]
  savedAt: number
}

export type ReviewQueuePosition = {
  index: number
  total: number
  prevId: number | null
  nextId: number | null
}

const safeStorage = () => {
  try {
    return window.localStorage
  } catch {
    return null
  }
}

export const normalizeIds = (ids: unknown): number[] => {
  if (!Array.isArray(ids)) return []
  const seen = new Set<number>()
  const out: number[] = []
  for (const raw of ids) {
    const id = Number(raw)
    if (!Number.isInteger(id) || id <= 0 || seen.has(id)) continue
    seen.add(id)
    out.push(id)
  }
  return out
}

const defaultClientFilter = (): ReviewClientFilter => ({ analysis: 'all', model: '' })

/** Build a queue state; paging is only possible when a list request is provided. */
export const createReviewQueueState = (
  ids: Array<number | null | undefined>,
  options: Partial<Omit<ReviewQueueState, 'ids' | 'savedAt'>> = {},
): ReviewQueueState => {
  const page = options.firstPage ?? 1
  return {
    ids: normalizeIds(ids),
    firstPage: page,
    lastPage: options.lastPage ?? page,
    totalPages: options.totalPages ?? page,
    shrinking: options.shrinking ?? false,
    request: options.request ?? null,
    clientFilter: options.clientFilter ?? defaultClientFilter(),
    exhaustedNext: options.exhaustedNext ?? false,
    suggestionIds: normalizeIds(options.suggestionIds ?? []),
    savedAt: Date.now(),
  }
}

export const saveReviewQueueState = (state: ReviewQueueState) => {
  const storage = safeStorage()
  if (!storage) return
  try {
    if (!state.ids.length) {
      storage.removeItem(QUEUE_KEY)
      return
    }
    storage.setItem(QUEUE_KEY, JSON.stringify({ ...state, savedAt: Date.now() }))
  } catch {
    // per-viewer convenience only
  }
}

export const loadReviewQueueState = (): ReviewQueueState | null => {
  const storage = safeStorage()
  if (!storage) return null
  try {
    const raw = storage.getItem(QUEUE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<ReviewQueueState>
      const ids = normalizeIds(parsed.ids)
      if (!ids.length) return null
      return createReviewQueueState(ids, {
        firstPage: Number(parsed.firstPage) || 1,
        lastPage: Number(parsed.lastPage) || 1,
        totalPages: Number(parsed.totalPages) || 1,
        shrinking: Boolean(parsed.shrinking),
        request: parsed.request ?? null,
        clientFilter: { ...defaultClientFilter(), ...parsed.clientFilter },
        exhaustedNext: Boolean(parsed.exhaustedNext),
        suggestionIds: normalizeIds(parsed.suggestionIds),
      })
    }
    // Lists remembered by an older version only carry ids.
    const legacy = storage.getItem(LEGACY_QUEUE_KEY)
    if (!legacy) return null
    const ids = normalizeIds((JSON.parse(legacy) as { ids?: unknown }).ids)
    return ids.length ? createReviewQueueState(ids) : null
  } catch {
    return null
  }
}

/** Ids-only convenience wrappers (no paging information). */
export const saveReviewQueue = (ids: Array<number | null | undefined>) =>
  saveReviewQueueState(createReviewQueueState(ids))

export const loadReviewQueue = (): number[] => loadReviewQueueState()?.ids ?? []

/** Position of `docId` in the remembered list, or null if it is not part of it. */
export const reviewQueuePosition = (
  ids: number[],
  docId: number,
): ReviewQueuePosition | null => {
  const index = ids.indexOf(docId)
  if (index === -1) return null
  return {
    index,
    total: ids.length,
    prevId: index > 0 ? (ids[index - 1] ?? null) : null,
    nextId: index < ids.length - 1 ? (ids[index + 1] ?? null) : null,
  }
}

export const readAutoAdvance = (): boolean => {
  const storage = safeStorage()
  if (!storage) return true
  try {
    return storage.getItem(AUTO_ADVANCE_KEY) !== '0'
  } catch {
    return true
  }
}

export const writeAutoAdvance = (value: boolean) => {
  const storage = safeStorage()
  if (!storage) return
  try {
    storage.setItem(AUTO_ADVANCE_KEY, value ? '1' : '0')
  } catch {
    // per-viewer convenience only
  }
}

export const isTypingTarget = (target: EventTarget | null): boolean => {
  const el = target as HTMLElement | null
  if (!el || typeof el.tagName !== 'string') return false
  const tag = el.tagName.toLowerCase()
  return tag === 'input' || tag === 'textarea' || tag === 'select' || el.isContentEditable === true
}
