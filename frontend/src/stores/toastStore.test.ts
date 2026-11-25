/* @vitest-environment jsdom */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useToastStore } from './toastStore'

describe('toastStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
  })

  it('merges identical toasts into one with a count', () => {
    const store = useToastStore()
    store.push('Request failed (500)', 'danger', 'Error')
    store.push('Request failed (500)', 'danger', 'Error')
    store.push('Request failed (500)', 'danger', 'Error')
    expect(store.toasts).toHaveLength(1)
    expect(store.toasts[0]?.count).toBe(3)
  })

  it('shows at most three toasts, dropping the oldest', () => {
    const store = useToastStore()
    for (const n of [1, 2, 3, 4]) store.push(`Message ${n}`)
    expect(store.toasts.map((t) => t.message)).toEqual(['Message 2', 'Message 3', 'Message 4'])
  })

  it('restarts the timer when a duplicate arrives', () => {
    const store = useToastStore()
    store.push('Saved', 'success', undefined, 1000)
    vi.advanceTimersByTime(800)
    store.push('Saved', 'success', undefined, 1000)
    vi.advanceTimersByTime(800)
    expect(store.toasts).toHaveLength(1)
    vi.advanceTimersByTime(300)
    expect(store.toasts).toHaveLength(0)
  })
})
