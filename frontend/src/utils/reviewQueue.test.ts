// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  isTypingTarget,
  loadReviewQueue,
  readAutoAdvance,
  reviewQueuePosition,
  saveReviewQueue,
  writeAutoAdvance,
} from './reviewQueue'

const createLocalStorageMock = () => {
  const store = new Map<string, string>()
  return {
    getItem: (key: string) => (store.has(key) ? (store.get(key) as string) : null),
    setItem: (key: string, value: string) => void store.set(key, String(value)),
    removeItem: (key: string) => void store.delete(key),
    clear: () => store.clear(),
  }
}

describe('reviewQueue storage', () => {
  beforeEach(() => {
    vi.stubGlobal('localStorage', createLocalStorageMock())
  })

  it('round-trips ordered unique ids and drops invalid values', () => {
    saveReviewQueue([5, 3, 3, 0, -1, null, undefined, 9])
    expect(loadReviewQueue()).toEqual([5, 3, 9])
  })

  it('clears the queue when saving an empty list', () => {
    saveReviewQueue([1, 2])
    saveReviewQueue([])
    expect(loadReviewQueue()).toEqual([])
  })

  it('survives corrupt stored data', () => {
    window.localStorage.setItem('review_queue_v1', '{not json')
    expect(loadReviewQueue()).toEqual([])
  })

  it('defaults auto-advance to on and persists the setting', () => {
    expect(readAutoAdvance()).toBe(true)
    writeAutoAdvance(false)
    expect(readAutoAdvance()).toBe(false)
    writeAutoAdvance(true)
    expect(readAutoAdvance()).toBe(true)
  })
})

describe('reviewQueuePosition', () => {
  const ids = [10, 20, 30]

  it('returns neighbors for a middle element', () => {
    expect(reviewQueuePosition(ids, 20)).toEqual({ index: 1, total: 3, prevId: 10, nextId: 30 })
  })

  it('has no previous at the start and no next at the end', () => {
    expect(reviewQueuePosition(ids, 10)?.prevId).toBeNull()
    expect(reviewQueuePosition(ids, 30)?.nextId).toBeNull()
  })

  it('returns null for documents outside the list', () => {
    expect(reviewQueuePosition(ids, 99)).toBeNull()
  })
})

describe('isTypingTarget', () => {
  it('detects form controls and contenteditable elements', () => {
    expect(isTypingTarget(document.createElement('input'))).toBe(true)
    expect(isTypingTarget(document.createElement('textarea'))).toBe(true)
    expect(isTypingTarget(document.createElement('select'))).toBe(true)
    expect(isTypingTarget(document.createElement('div'))).toBe(false)
    expect(isTypingTarget(null)).toBe(false)
  })
})
