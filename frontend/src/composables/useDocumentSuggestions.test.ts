import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const suggestFieldVariants = vi.fn()
const fetchFieldVariants = vi.fn()

vi.mock('@tanstack/vue-query', () => ({
  useMutation: (options: { mutationFn: (vars: unknown) => Promise<unknown> }) => ({
    mutateAsync: (vars: unknown) => options.mutationFn(vars),
  }),
}))
vi.mock('../services/prefetchCache', () => ({ takePrefetchedSuggestions: () => null }))
vi.mock('../services/documents', () => ({
  applyFieldSuggestion: vi.fn(),
  applySuggestionToDocument: vi.fn(),
  getSuggestions: vi.fn(),
  suggestFieldVariants: (...args: unknown[]) => suggestFieldVariants(...args),
  fetchFieldVariants: (...args: unknown[]) => fetchFieldVariants(...args),
}))

import {
  VARIANT_POLL_INTERVAL_MS,
  VARIANT_POLL_TIMEOUT_MS,
  useDocumentSuggestions,
} from './useDocumentSuggestions'

const OLD = '2026-10-11T10:00:00+00:00'
const NEW = '2026-10-11T10:00:20+00:00'

describe('queued "Suggest new" polling', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    suggestFieldVariants.mockReset()
    fetchFieldVariants.mockReset()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('ignores the previous batch and waits for the new one', async () => {
    suggestFieldVariants.mockResolvedValue({ queued: true, updated_at: OLD })
    fetchFieldVariants
      .mockResolvedValueOnce({ variants: ['Old A'], updated_at: OLD })
      .mockResolvedValueOnce({ variants: ['Old A'], updated_at: OLD })
      .mockResolvedValueOnce({ variants: ['New A', 'New B'], updated_at: NEW })
    const { suggestField, suggestionVariants, suggestionVariantLoading, suggestionVariantWait } =
      useDocumentSuggestions()

    const run = suggestField(1, 'paperless_ocr', 'title')
    await vi.advanceTimersByTimeAsync(VARIANT_POLL_INTERVAL_MS)
    expect(suggestionVariants.value['paperless_ocr:title']).toBeUndefined()
    expect(suggestionVariantLoading.value['paperless_ocr:title']).toBe(true)
    await vi.advanceTimersByTimeAsync(VARIANT_POLL_INTERVAL_MS)
    expect(suggestionVariantWait.value['paperless_ocr:title']).toBeGreaterThanOrEqual(3)
    await vi.advanceTimersByTimeAsync(VARIANT_POLL_INTERVAL_MS)
    await run

    expect(suggestionVariants.value['paperless_ocr:title']).toEqual(['New A', 'New B'])
    expect(suggestionVariantLoading.value['paperless_ocr:title']).toBe(false)
    expect(suggestionVariantWait.value['paperless_ocr:title']).toBe(0)
  })

  it('accepts the first batch when none existed before', async () => {
    suggestFieldVariants.mockResolvedValue({ queued: true, updated_at: null })
    fetchFieldVariants.mockResolvedValue({ variants: ['First'], updated_at: NEW })
    const { suggestField, suggestionVariants } = useDocumentSuggestions()

    const run = suggestField(1, 'vision_ocr', 'date')
    await vi.advanceTimersByTimeAsync(VARIANT_POLL_INTERVAL_MS)
    await run

    expect(suggestionVariants.value['vision_ocr:date']).toEqual(['First'])
  })

  it('tells the reviewer when the model takes too long instead of failing silently', async () => {
    suggestFieldVariants.mockResolvedValue({ queued: true, updated_at: OLD })
    fetchFieldVariants.mockResolvedValue({ variants: ['Old A'], updated_at: OLD })
    const { suggestField, suggestionVariants, suggestionVariantError } = useDocumentSuggestions()

    const run = suggestField(1, 'paperless_ocr', 'title')
    await vi.advanceTimersByTimeAsync(VARIANT_POLL_TIMEOUT_MS + VARIANT_POLL_INTERVAL_MS * 2)
    await run

    expect(suggestionVariants.value['paperless_ocr:title']).toBeUndefined()
    expect(suggestionVariantError.value['paperless_ocr:title']).toContain('still working')
  })

  it('shows direct (non-queued) variants without polling', async () => {
    suggestFieldVariants.mockResolvedValue({ variants: ['Direct'] })
    const { suggestField, suggestionVariants } = useDocumentSuggestions()

    await suggestField(1, 'paperless_ocr', 'title')

    expect(suggestionVariants.value['paperless_ocr:title']).toEqual(['Direct'])
    expect(fetchFieldVariants).not.toHaveBeenCalled()
  })
})
