const QUEUE_KEY = 'review_queue_v1'
const AUTO_ADVANCE_KEY = 'review_auto_advance'

export type StoredReviewQueue = {
  ids: number[]
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

const normalizeIds = (ids: unknown): number[] => {
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

/** Remember the ordered ids of the list the user opened a document from. */
export const saveReviewQueue = (ids: Array<number | null | undefined>) => {
  const storage = safeStorage()
  if (!storage) return
  const normalized = normalizeIds(ids)
  try {
    if (!normalized.length) {
      storage.removeItem(QUEUE_KEY)
      return
    }
    const payload: StoredReviewQueue = { ids: normalized, savedAt: Date.now() }
    storage.setItem(QUEUE_KEY, JSON.stringify(payload))
  } catch {
    // per-viewer convenience only
  }
}

export const loadReviewQueue = (): number[] => {
  const storage = safeStorage()
  if (!storage) return []
  try {
    const raw = storage.getItem(QUEUE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as Partial<StoredReviewQueue>
    return normalizeIds(parsed.ids)
  } catch {
    return []
  }
}

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
