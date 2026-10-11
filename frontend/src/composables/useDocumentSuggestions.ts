import { ref } from 'vue'
import { useMutation } from '@tanstack/vue-query'
import { takePrefetchedSuggestions } from '../services/prefetchCache'
import {
  applyFieldSuggestion,
  applySuggestionToDocument,
  fetchFieldVariants,
  getSuggestions,
  suggestFieldVariants,
} from '../services/documents'

type SuggestionPayload = Record<string, unknown>
type SuggestionsState = {
  paperless_ocr?: SuggestionPayload
  vision_ocr?: SuggestionPayload
  similar_docs?: SuggestionPayload
  suggestions_meta?: Record<string, unknown>
}

const errorMessage = (err: unknown, fallback: string) => {
  if (err instanceof Error) return err.message || fallback
  if (typeof err === 'string') return err || fallback
  return fallback
}

const extractVariants = (data: unknown): unknown[] => {
  if (!data || typeof data !== 'object') return []
  const root = data as { variants?: unknown }
  const variantsContainer = root.variants
  if (Array.isArray(variantsContainer)) return variantsContainer
  if (!variantsContainer || typeof variantsContainer !== 'object') return []
  const parsed = (variantsContainer as { parsed?: { variants?: unknown[] } }).parsed
  if (Array.isArray(parsed?.variants)) return parsed.variants
  const direct = (variantsContainer as { variants?: unknown[] }).variants
  if (Array.isArray(direct)) return direct
  return []
}

const isQueued = (data: unknown) =>
  typeof data === 'object' &&
  data !== null &&
  'queued' in data &&
  Boolean((data as { queued?: boolean }).queued)

/** Reviewer input for "Suggest new": a marked passage of the text and a short hint. */
export type SuggestGuidance = {
  focus_text?: string
  hint?: string
  /** OCR text the model reads (default: the text of the panel the request comes from). */
  text_source?: 'paperless_ocr' | 'vision_ocr'
  /** Only these pages are sent to the model, e.g. "1" or "1-2,4". */
  pages?: string
}

/** How often and how long a queued "Suggest new" request is polled for its result. */
export const VARIANT_POLL_INTERVAL_MS = 1500
export const VARIANT_POLL_TIMEOUT_MS = 120_000

export const useDocumentSuggestions = () => {
  const suggestions = ref<SuggestionsState | null>(null)
  const suggestionsLoading = ref(false)
  const suggestionsError = ref('')
  const suggestionVariants = ref<Record<string, unknown[]>>({})
  const suggestionVariantLoading = ref<Record<string, boolean>>({})
  const suggestionVariantError = ref<Record<string, string>>({})
  /** Seconds a queued request has been waiting, per `source:field` (feedback while polling). */
  const suggestionVariantWait = ref<Record<string, number>>({})

  const loadSuggestionsMutation = useMutation({
    mutationFn: ({ id, source }: { id: number; source?: 'paperless_ocr' | 'vision_ocr' }) =>
      source
        ? getSuggestions(id, { source, refresh: true, priority: true, include_similar: true })
        : (takePrefetchedSuggestions(id) ?? getSuggestions(id, { include_similar: true })),
  })
  const suggestFieldMutation = useMutation({
    mutationFn: ({
      id,
      source,
      field,
      guidance,
    }: {
      id: number
      source: 'paperless_ocr' | 'vision_ocr'
      field: string
      guidance?: SuggestGuidance
    }) =>
      suggestFieldVariants(
        id,
        {
          source,
          field,
          count: 3,
          ...(guidance?.focus_text ? { focus_text: guidance.focus_text } : {}),
          ...(guidance?.hint ? { hint: guidance.hint } : {}),
          ...(guidance?.text_source ? { text_source: guidance.text_source } : {}),
          ...(guidance?.pages ? { pages: guidance.pages } : {}),
        },
        true,
      ),
  })
  const applyFieldSuggestionMutation = useMutation({
    mutationFn: ({
      id,
      source,
      field,
      value,
    }: {
      id: number
      source: 'paperless_ocr' | 'vision_ocr'
      field: string
      value: unknown
    }) => applyFieldSuggestion(id, { source, field, value }),
  })
  const applySuggestionMutation = useMutation({
    mutationFn: ({
      id,
      payload,
    }: {
      id: number
      payload: { source?: string; field: string; value: unknown }
    }) => applySuggestionToDocument(id, payload),
  })

  const resetSuggestionsState = () => {
    suggestions.value = null
    suggestionsError.value = ''
    suggestionVariants.value = {}
    suggestionVariantLoading.value = {}
    suggestionVariantError.value = {}
    suggestionVariantWait.value = {}
  }

  const loadSuggestions = async (id: number) => {
    suggestionsLoading.value = true
    suggestionsError.value = ''
    try {
      const data = await loadSuggestionsMutation.mutateAsync({ id })
      const meta = (data as { suggestions_meta?: Record<string, unknown> }).suggestions_meta
      suggestions.value = data.suggestions
        ? { ...data.suggestions, suggestions_meta: meta }
        : null
    } catch (err: unknown) {
      suggestionsError.value = errorMessage(err, 'Failed to load suggestions')
    } finally {
      suggestionsLoading.value = false
    }
  }

  const refreshSuggestions = async (id: number, source: 'paperless_ocr' | 'vision_ocr') => {
    suggestionsLoading.value = true
    suggestionsError.value = ''
    try {
      const data = await loadSuggestionsMutation.mutateAsync({ id, source })
      const meta = (data as { suggestions_meta?: Record<string, unknown> }).suggestions_meta
      suggestions.value = data.suggestions
        ? { ...data.suggestions, suggestions_meta: meta }
        : null
    } catch (err: unknown) {
      suggestionsError.value = errorMessage(err, 'Failed to refresh suggestions')
    } finally {
      suggestionsLoading.value = false
    }
  }

  /**
   * Wait for a queued request. The variant store already holds the previous batch, so the
   * result is only taken once its version stamp differs from the one at enqueue time.
   */
  const pollVariants = async (
    id: number,
    source: 'paperless_ocr' | 'vision_ocr',
    field: string,
    baseline: string | null,
  ) => {
    const key = `${source}:${field}`
    const startedAt = Date.now()
    while (Date.now() - startedAt < VARIANT_POLL_TIMEOUT_MS) {
      await new Promise((resolve) => setTimeout(resolve, VARIANT_POLL_INTERVAL_MS))
      suggestionVariantWait.value = {
        ...suggestionVariantWait.value,
        [key]: Math.round((Date.now() - startedAt) / 1000),
      }
      try {
        const data = await fetchFieldVariants(id, source, field)
        const variants = Array.isArray(data.variants) ? data.variants : []
        const stampKnown = 'updated_at' in data
        const stamp = data.updated_at ?? null
        if (variants.length > 0 && (!stampKnown || stamp !== baseline)) {
          suggestionVariants.value = { ...suggestionVariants.value, [key]: variants }
          return
        }
      } catch (err: unknown) {
        suggestionVariantError.value = {
          ...suggestionVariantError.value,
          [key]: errorMessage(err, 'Failed to fetch variants'),
        }
        return
      }
    }
    suggestionVariantError.value = {
      ...suggestionVariantError.value,
      [key]:
        'The model is still working on this request. Check the Queue, then press "Suggest new" again to fetch the result.',
    }
  }

  const suggestField = async (
    id: number,
    source: 'paperless_ocr' | 'vision_ocr',
    field: string,
    guidance?: SuggestGuidance,
  ) => {
    const key = `${source}:${field}`
    suggestionVariantLoading.value = { ...suggestionVariantLoading.value, [key]: true }
    suggestionVariantError.value = { ...suggestionVariantError.value, [key]: '' }
    try {
      const data = await suggestFieldMutation.mutateAsync({ id, source, field, guidance })
      const directVariants = (data as { variants?: unknown }).variants
      const variants = Array.isArray(directVariants) ? directVariants : extractVariants(data)
      if (variants.length) {
        suggestionVariants.value = { ...suggestionVariants.value, [key]: variants }
      } else if (isQueued(data)) {
        const stamp = (data as { updated_at?: string | null }).updated_at ?? null
        await pollVariants(id, source, field, stamp)
      }
    } catch (err: unknown) {
      suggestionVariantError.value = {
        ...suggestionVariantError.value,
        [key]: errorMessage(err, 'Failed to generate variants'),
      }
    } finally {
      suggestionVariantLoading.value = { ...suggestionVariantLoading.value, [key]: false }
      suggestionVariantWait.value = { ...suggestionVariantWait.value, [key]: 0 }
    }
  }

  const applyVariant = async (
    id: number,
    source: 'paperless_ocr' | 'vision_ocr',
    field: string,
    value: unknown,
  ) => {
    suggestionsLoading.value = true
    suggestionsError.value = ''
    try {
      const data = await applyFieldSuggestionMutation.mutateAsync({ id, source, field, value })
      const nextSuggestions = (data as { suggestions?: SuggestionsState }).suggestions
      if (nextSuggestions) {
        suggestions.value = { ...suggestions.value, ...nextSuggestions }
      }
    } catch (err: unknown) {
      suggestionsError.value = errorMessage(err, 'Failed to apply suggestion')
    } finally {
      suggestionsLoading.value = false
    }
  }

  const applyToDocument = async (
    id: number,
    payload: { source?: string; field: string; value: unknown },
  ) => {
    await applySuggestionMutation.mutateAsync({ id, payload })
  }

  return {
    suggestions,
    suggestionsLoading,
    suggestionsError,
    suggestionVariants,
    suggestionVariantLoading,
    suggestionVariantError,
    suggestionVariantWait,
    resetSuggestionsState,
    loadSuggestions,
    refreshSuggestions,
    suggestField,
    applyVariant,
    applyToDocument,
  }
}
