// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { clearLastPreset, readLastPreset, writeLastPreset } from './documentsPresetStorage'

const createLocalStorageMock = () => {
  const store = new Map<string, string>()
  return {
    getItem: (key: string) => (store.has(key) ? (store.get(key) as string) : null),
    setItem: (key: string, value: string) => void store.set(key, String(value)),
    removeItem: (key: string) => void store.delete(key),
    clear: () => store.clear(),
  }
}

beforeEach(() => {
  vi.stubGlobal('localStorage', createLocalStorageMock())
})

describe('documentsPresetStorage', () => {
  it('round-trips a valid preset key', () => {
    writeLastPreset('unreviewed')
    expect(readLastPreset()).toBe('unreviewed')
  })

  it('returns an empty string for an unknown or missing value', () => {
    expect(readLastPreset()).toBe('')
    window.localStorage.setItem('documents.lastPreset', 'not_a_preset')
    expect(readLastPreset()).toBe('')
  })

  it('ignores a raw invalid value stored under the key', () => {
    window.localStorage.setItem('documents.lastPreset', 'bogus')
    expect(readLastPreset()).toBe('')
  })

  it('clears a previously stored preset', () => {
    writeLastPreset('needs_review')
    clearLastPreset()
    expect(readLastPreset()).toBe('')
  })
})
