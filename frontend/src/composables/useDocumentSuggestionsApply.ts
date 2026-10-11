import type { Ref } from 'vue'
import type { SuggestionApplyItem } from '../utils/suggestionSelection'

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

  const applySelected = async (items: SuggestionApplyItem[]) => {
    const applied: string[] = []
    const failed: Array<{ field: string; message: string }> = []
    if (!items.length) return { applied, failed }
    const reloadSuggestions = Boolean(args.suggestions.value)
    const reloadPages = args.pageTexts.value.length > 0
    const reloadQuality = Boolean(args.contentQuality.value)
    const docId = resolveDocId()
    for (const item of items) {
      try {
        await args.applySuggestionToDocument(docId, item)
        applied.push(item.field)
      } catch (err: unknown) {
        failed.push({
          field: item.field,
          message: args.toErrorMessage(err, 'Failed to apply suggestion to document'),
        })
      }
    }
    if (failed.length) {
      args.suggestionsError.value = failed.map((f) => `${f.field}: ${f.message}`).join('; ')
    }
    if (applied.length) {
      await args.loadDocument()
      if (reloadSuggestions) await args.loadSuggestionsForDoc()
      if (reloadPages) await args.loadPageTextsForDoc()
      if (reloadQuality) await args.loadContentQualityForDoc()
    }
    return { applied, failed }
  }

  return {
    applyVariantOnly,
    applyVariantToDocument,
    applyToDocument,
    applySelected,
  }
}
