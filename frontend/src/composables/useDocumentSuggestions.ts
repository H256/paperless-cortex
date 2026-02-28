import { ref } from 'vue'
import { useMutation } from '@tanstack/vue-query'
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

export const useDocumentSuggestions = () => {
  const suggestions = ref<SuggestionsState | null>(null)
  const suggestionsLoading = ref(false)
  const suggestionsError = ref('')
  const suggestionVariants = ref<Record<string, unknown[]>>({})
  const suggestionVariantLoading = ref<Record<string, boolean>>({})
  const suggestionVariantError = ref<Record<string, string>>({})

  const loadSuggestionsMutation = useMutation({
    mutationFn: ({ id, source }: { id: number; source?: 'paperless_ocr' | 'vision_ocr' }) =>
      source
        ? getSuggestions(id, { source, refresh: true, priority: true, include_similar: true })
        : getSuggestions(id, { include_similar: true }),
  })
  const suggestFieldMutation = useMutation({
    mutationFn: ({
      id,
      source,
      field,
    }: {
      id: number
      source: 'paperless_ocr' | 'vision_ocr'
      field: string
    }) => suggestFieldVariants(id, { source, field, count: 3 }, true),
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

  const pollVariants = async (id: number, source: 'paperless_ocr' | 'vision_ocr', field: string) => {
    const key = `${source}:${field}`
    for (let attempt = 0; attempt < 10; attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, 1200))
      try {
        const data = await fetchFieldVariants(id, source, field)
        if (Array.isArray(data.variants) && data.variants.length) {
          suggestionVariants.value = { ...suggestionVariants.value, [key]: data.variants }
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
  }

  const suggestField = async (id: number, source: 'paperless_ocr' | 'vision_ocr', field: string) => {
    const key = `${source}:${field}`
    suggestionVariantLoading.value = { ...suggestionVariantLoading.value, [key]: true }
    suggestionVariantError.value = { ...suggestionVariantError.value, [key]: '' }
    try {
      const data = await suggestFieldMutation.mutateAsync({ id, source, field })
      const directVariants = (data as { variants?: unknown }).variants
      const variants = Array.isArray(directVariants) ? directVariants : extractVariants(data)
      if (variants.length) {
        suggestionVariants.value = { ...suggestionVariants.value, [key]: variants }
      } else if (isQueued(data)) {
        await pollVariants(id, source, field)
      }
    } catch (err: unknown) {
      suggestionVariantError.value = {
        ...suggestionVariantError.value,
        [key]: errorMessage(err, 'Failed to generate variants'),
      }
    } finally {
      suggestionVariantLoading.value = { ...suggestionVariantLoading.value, [key]: false }
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
    resetSuggestionsState,
    loadSuggestions,
    refreshSuggestions,
    suggestField,
    applyVariant,
    applyToDocument,
  }
}
