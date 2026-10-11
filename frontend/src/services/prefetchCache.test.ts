import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPrefetchCache } from './prefetchCache'

describe('createPrefetchCache', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('returns a prefetched value exactly once', async () => {
    const cache = createPrefetchCache<string>()
    const load = vi.fn(async () => 'doc-5')
    cache.prefetch(5, load)
    cache.prefetch(5, load)
    expect(load).toHaveBeenCalledTimes(1)

    const first = cache.take(5)
    expect(first).not.toBeNull()
    await expect(first).resolves.toBe('doc-5')
    expect(cache.take(5)).toBeNull()
  })

  it('drops entries after the ttl so a later reload never gets stale data', () => {
    const cache = createPrefetchCache<string>(1_000)
    cache.prefetch(1, async () => 'x')
    vi.advanceTimersByTime(1_500)
    expect(cache.take(1)).toBeNull()
  })

  it('removes failed prefetches', async () => {
    const cache = createPrefetchCache<string>()
    cache.prefetch(2, () => Promise.reject(new Error('boom')))
    await Promise.resolve()
    await Promise.resolve()
    expect(cache.take(2)).toBeNull()
  })

  it('keeps at most maxEntries entries', () => {
    const cache = createPrefetchCache<number>(20_000, 2)
    cache.prefetch(1, async () => 1)
    cache.prefetch(2, async () => 2)
    cache.prefetch(3, async () => 3)
    expect(cache.size()).toBe(2)
    expect(cache.take(1)).toBeNull()
    expect(cache.take(3)).not.toBeNull()
  })
})
