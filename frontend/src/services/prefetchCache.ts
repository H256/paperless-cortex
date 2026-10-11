import { getDocumentLocal, getSuggestions } from './documents'

type Entry<T> = { promise: Promise<T>; at: number }

/**
 * Short-lived, single-use cache for data that was requested ahead of time.
 * An entry is removed when it is taken, when it fails or when it is older than `ttlMs`,
 * so a reload after an edit can never be answered with stale prefetched data.
 */
export const createPrefetchCache = <T>(ttlMs = 20_000, maxEntries = 6) => {
  const entries = new Map<number, Entry<T>>()

  const prune = (now: number) => {
    for (const [key, entry] of entries) {
      if (now - entry.at > ttlMs) entries.delete(key)
    }
    while (entries.size > maxEntries) {
      const oldest = entries.keys().next().value
      if (oldest === undefined) break
      entries.delete(oldest)
    }
  }

  const prefetch = (id: number, load: () => Promise<T>) => {
    const now = Date.now()
    prune(now)
    if (entries.has(id)) return
    const promise = load()
    entries.set(id, { promise, at: now })
    prune(now)
    promise.catch(() => {
      if (entries.get(id)?.promise === promise) entries.delete(id)
    })
  }

  const take = (id: number): Promise<T> | null => {
    prune(Date.now())
    const entry = entries.get(id)
    if (!entry) return null
    entries.delete(id)
    return entry.promise
  }

  const clear = () => entries.clear()

  return { prefetch, take, clear, size: () => entries.size }
}

type DocumentPayload = Awaited<ReturnType<typeof getDocumentLocal>>
type SuggestionsPayload = Awaited<ReturnType<typeof getSuggestions>>

const documentCache = createPrefetchCache<DocumentPayload>()
const suggestionsCache = createPrefetchCache<SuggestionsPayload>()

export const prefetchDocument = (id: number) =>
  documentCache.prefetch(id, () => getDocumentLocal(id))

export const prefetchSuggestions = (id: number) =>
  suggestionsCache.prefetch(id, () => getSuggestions(id, { include_similar: true }))

export const takePrefetchedDocument = (id: number) => documentCache.take(id)
export const takePrefetchedSuggestions = (id: number) => suggestionsCache.take(id)
