/* @vitest-environment jsdom */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useErrorStore } from './errorStore'

describe('errorStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
  })

  it('merges identical errors into one with a count', () => {
    const store = useErrorStore()
    for (let i = 0; i < 5; i += 1) store.add('Request failed (500)')
    expect(store.errors).toHaveLength(1)
    expect(store.errors[0]?.count).toBe(5)
  })

  it('keeps the three newest distinct errors', () => {
    const store = useErrorStore()
    for (const n of [1, 2, 3, 4]) store.add(`Error ${n}`)
    expect(store.errors.map((e) => e.message)).toEqual(['Error 4', 'Error 3', 'Error 2'])
  })

  it('removes an error after its ttl, restarting on a duplicate', () => {
    const store = useErrorStore()
    store.add('Offline', undefined, 1000)
    vi.advanceTimersByTime(800)
    store.add('Offline', undefined, 1000)
    vi.advanceTimersByTime(800)
    expect(store.errors).toHaveLength(1)
    vi.advanceTimersByTime(300)
    expect(store.errors).toHaveLength(0)
  })
})
