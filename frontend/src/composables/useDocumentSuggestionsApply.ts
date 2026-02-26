import type { Ref } from 'vue'

type UseDocumentSuggestionsApplyArgs = {
  docId: number | (() => number)
  suggestions: Ref<unknown>
  pageTexts: Ref<Array<unknown>>
  contentQuality: Ref<unknown>
  suggestionsError: Ref<string>
  applyVariant: (
    docId: number,
    source: 'paperless_ocr' | 'vision_ocr',
    field: string,
    value: unknown,
  ) => Promise<void>
  applySuggestionToDocument: (
    docId: number,
    payload: { source: string; field: string; value: unknown },
  ) => Promise<void>
  loadDocument: () => Promise<void>
  loadSuggestionsForDoc: () => Promise<void>
  loadPageTextsForDoc: () => Promise<void>
  loadContentQualityForDoc: () => Promise<void>
  toErrorMessage: (err: unknown, fallback: string) => string
}

export const useDocumentSuggestionsApply = (args: UseDocumentSuggestionsApplyArgs) => {
  const resolveDocId = () => (typeof args.docId === 'function' ? args.docId() : args.docId)

  const applyVariantOnly = async (
    source: 'paperless_ocr' | 'vision_ocr',
    field: string,
    value: unknown,
  ) => {
    await args.applyVariant(resolveDocId(), source, field, value)
  }

  const applyVariantToDocument = async (
    source: 'paperless_ocr' | 'vision_ocr',
    field: string,
    value: unknown,
  ) => {
    const docId = resolveDocId()
    await args.applyVariant(docId, source, field, value)
    await args.applySuggestionToDocument(docId, { source, field, value })
    await args.loadDocument()
    await args.loadSuggestionsForDoc()
  }

  const applyToDocument = async (source: string, field: string, value: unknown) => {
    try {
      const reloadSuggestions = Boolean(args.suggestions.value)
      const reloadPages = args.pageTexts.value.length > 0
      const reloadQuality = Boolean(args.contentQuality.value)
      await args.applySuggestionToDocument(resolveDocId(), { source, field, value })
      await args.loadDocument()
      if (reloadSuggestions) {
        await args.loadSuggestionsForDoc()
      }
      if (reloadPages) {
        await args.loadPageTextsForDoc()
      }
      if (reloadQuality) {
        await args.loadContentQualityForDoc()
      }
    } catch (err: unknown) {
      args.suggestionsError.value = args.toErrorMessage(err, 'Failed to apply suggestion to document')
    }
  }

  return {
    applyVariantOnly,
    applyVariantToDocument,
    applyToDocument,
  }
}
