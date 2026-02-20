import { describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import { useDocumentSuggestionsApply } from './useDocumentSuggestionsApply'

const createHarness = () => {
  const suggestions = ref<unknown>({})
  const pageTexts = ref<Array<unknown>>([])
  const contentQuality = ref<unknown>(null)
  const suggestionsError = ref('')

  const applyVariant = vi.fn(async () => undefined)
  const applySuggestionToDocument = vi.fn(async () => undefined)
  const loadDocument = vi.fn(async () => undefined)
  const loadSuggestionsForDoc = vi.fn(async () => undefined)
  const loadPageTextsForDoc = vi.fn(async () => undefined)
  const loadContentQualityForDoc = vi.fn(async () => undefined)
  const toErrorMessage = vi.fn((err: unknown, fallback: string) =>
    err instanceof Error ? err.message : fallback,
  )

  const composable = useDocumentSuggestionsApply({
    docId: 12,
    suggestions,
    pageTexts,
    contentQuality,
    suggestionsError,
    applyVariant,
    applySuggestionToDocument,
    loadDocument,
    loadSuggestionsForDoc,
    loadPageTextsForDoc,
    loadContentQualityForDoc,
    toErrorMessage,
  })

  return {
    suggestions,
    pageTexts,
    contentQuality,
    suggestionsError,
    applyVariant,
    applySuggestionToDocument,
    loadDocument,
    loadSuggestionsForDoc,
    loadPageTextsForDoc,
    loadContentQualityForDoc,
    toErrorMessage,
    composable,
  }
}

describe('useDocumentSuggestionsApply', () => {
  it('applyVariantOnly forwards variant call', async () => {
    const { composable, applyVariant } = createHarness()
    await composable.applyVariantOnly('vision_ocr', 'title', 'New title')
    expect(applyVariant).toHaveBeenCalledWith(12, 'vision_ocr', 'title', 'New title')
  })

  it('applyVariantToDocument persists then reloads doc + suggestions', async () => {
    const {
      composable,
      applyVariant,
      applySuggestionToDocument,
      loadDocument,
      loadSuggestionsForDoc,
    } = createHarness()
    await composable.applyVariantToDocument('paperless_ocr', 'correspondent', 'ACME')
    expect(applyVariant).toHaveBeenCalledWith(12, 'paperless_ocr', 'correspondent', 'ACME')
    expect(applySuggestionToDocument).toHaveBeenCalledWith(12, {
      source: 'paperless_ocr',
      field: 'correspondent',
      value: 'ACME',
    })
    expect(loadDocument).toHaveBeenCalled()
    expect(loadSuggestionsForDoc).toHaveBeenCalled()
  })

  it('applyToDocument runs conditional reload matrix', async () => {
    const {
      composable,
      suggestions,
      pageTexts,
      contentQuality,
      applySuggestionToDocument,
      loadDocument,
      loadSuggestionsForDoc,
      loadPageTextsForDoc,
      loadContentQualityForDoc,
    } = createHarness()
    suggestions.value = { any: true }
    pageTexts.value = [{ page: 1 }]
    contentQuality.value = { score: 80 }

    await composable.applyToDocument('vision_ocr', 'tags', ['A'])

    expect(applySuggestionToDocument).toHaveBeenCalledWith(12, {
      source: 'vision_ocr',
      field: 'tags',
      value: ['A'],
    })
    expect(loadDocument).toHaveBeenCalled()
    expect(loadSuggestionsForDoc).toHaveBeenCalled()
    expect(loadPageTextsForDoc).toHaveBeenCalled()
    expect(loadContentQualityForDoc).toHaveBeenCalled()
  })

  it('applyToDocument maps errors into suggestionsError', async () => {
    const { composable, applySuggestionToDocument, suggestionsError, toErrorMessage } = createHarness()
    applySuggestionToDocument.mockRejectedValueOnce(new Error('persist failed'))
    await composable.applyToDocument('vision_ocr', 'title', 'x')
    expect(toErrorMessage).toHaveBeenCalled()
    expect(suggestionsError.value).toBe('persist failed')
  })

  it('applyToDocument uses fallback message for non-Error throws', async () => {
    const { composable, applySuggestionToDocument, suggestionsError } = createHarness()
    applySuggestionToDocument.mockRejectedValueOnce('raw failure')
    await composable.applyToDocument('vision_ocr', 'title', 'x')
    expect(suggestionsError.value).toBe('Failed to apply suggestion to document')
  })

  it('applyToDocument avoids optional reloads when suggestion/text/quality are empty', async () => {
    const {
      composable,
      suggestions,
      pageTexts,
      contentQuality,
      loadDocument,
      loadSuggestionsForDoc,
      loadPageTextsForDoc,
      loadContentQualityForDoc,
    } = createHarness()
    suggestions.value = null
    pageTexts.value = []
    contentQuality.value = null

    await composable.applyToDocument('paperless_ocr', 'title', 'Clean')

    expect(loadDocument).toHaveBeenCalled()
    expect(loadSuggestionsForDoc).not.toHaveBeenCalled()
    expect(loadPageTextsForDoc).not.toHaveBeenCalled()
    expect(loadContentQualityForDoc).not.toHaveBeenCalled()
  })
})
