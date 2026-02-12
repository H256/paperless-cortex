import { ref } from 'vue'
import { useMutation } from '@tanstack/vue-query'
import {
  type DocumentDetail,
  type DocumentType,
  type PageText,
  type VisionProgress,
  type Tag,
  type Correspondent,
  applyFieldSuggestion,
  applySuggestionToDocument,
  fetchFieldVariants,
  getCorrespondents,
  getDocumentLocal,
  getDocumentType,
  getPageTexts,
  getSuggestions,
  getTags,
  getTextQuality,
  getOcrScores,
  suggestFieldVariants,
} from '../services/documents'
import type { DocumentOcrScoreOut, TextQualityMetrics } from '@/api/generated/model'

type SuggestionPayload = Record<string, unknown>
type SuggestionsState = {
  paperless_ocr?: SuggestionPayload
  vision_ocr?: SuggestionPayload
  best_pick?: SuggestionPayload
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

export const useDocumentDetailData = () => {
  const document = ref<DocumentDetail | null>(null)
  const loading = ref(false)
  const syncing = ref(false)
  const tags = ref<Tag[]>([])
  const correspondents = ref<Correspondent[]>([])
  const docTypes = ref<DocumentType[]>([])
  const pageTexts = ref<PageText[]>([])
  const pageTextsVisionProgress = ref<VisionProgress | null>(null)
  const pageTextsLoading = ref(false)
  const pageTextsError = ref('')
  const contentQuality = ref<TextQualityMetrics | null>(null)
  const contentQualityLoading = ref(false)
  const contentQualityError = ref('')
  const ocrScores = ref<DocumentOcrScoreOut[]>([])
  const ocrScoresLoading = ref(false)
  const ocrScoresError = ref('')
  const suggestions = ref<SuggestionsState | null>(null)
  const suggestionsLoading = ref(false)
  const suggestionsError = ref('')
  const suggestionVariants = ref<Record<string, unknown[]>>({})
  const suggestionVariantLoading = ref<Record<string, boolean>>({})
  const suggestionVariantError = ref<Record<string, string>>({})

  const loadDocumentMutation = useMutation({
    mutationFn: (id: number) => getDocumentLocal(id),
  })
  const loadMetaMutation = useMutation({
    mutationFn: async () => {
      const [tagsResp, corrResp] = await Promise.all([getTags(), getCorrespondents()])
      let fetchedDocType: DocumentType | null = null
      if (document.value?.document_type) {
        fetchedDocType = await getDocumentType(document.value.document_type)
      }
      return {
        tags: tagsResp.results ?? [],
        correspondents: corrResp.results ?? [],
        docType: fetchedDocType,
      }
    },
  })
  const loadPageTextsMutation = useMutation({
    mutationFn: ({ id, priority }: { id: number; priority: boolean }) => getPageTexts(id, priority),
  })
  const loadContentQualityMutation = useMutation({
    mutationFn: ({ id, priority }: { id: number; priority: boolean }) => getTextQuality(id, priority),
  })
  const loadOcrScoresMutation = useMutation({
    mutationFn: ({ id, refresh }: { id: number; refresh: boolean }) =>
      getOcrScores(id, refresh ? { refresh } : undefined),
  })
  const loadSuggestionsMutation = useMutation({
    mutationFn: ({ id, source }: { id: number; source?: 'paperless_ocr' | 'vision_ocr' }) =>
      source
        ? getSuggestions(id, { source, refresh: true, priority: true })
        : getSuggestions(id),
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

  const loadDocument = async (id: number) => {
    loading.value = true
    try {
      const data = await loadDocumentMutation.mutateAsync(id)
      if (data?.status === 'missing') {
        document.value = null
      } else {
        document.value = data
      }
      pageTexts.value = []
      pageTextsVisionProgress.value = null
      pageTextsError.value = ''
      contentQuality.value = null
      contentQualityError.value = ''
      ocrScores.value = []
      ocrScoresLoading.value = false
      ocrScoresError.value = ''
      suggestions.value = null
      suggestionsError.value = ''
      suggestionVariants.value = {}
      suggestionVariantLoading.value = {}
      suggestionVariantError.value = {}
    } finally {
      loading.value = false
    }
  }

  const loadMeta = async () => {
    const data = await loadMetaMutation.mutateAsync()
    tags.value = data.tags
    correspondents.value = data.correspondents
    docTypes.value = data.docType ? [data.docType] : []
  }

  const loadPageTexts = async (id: number, priority = false) => {
    pageTextsLoading.value = true
    pageTextsError.value = ''
    try {
      const data = await loadPageTextsMutation.mutateAsync({ id, priority })
      pageTexts.value = data.pages ?? []
      pageTextsVisionProgress.value = data.vision_progress ?? null
    } catch (err: unknown) {
      pageTextsError.value = errorMessage(err, 'Failed to load page texts')
      pageTextsVisionProgress.value = null
    } finally {
      pageTextsLoading.value = false
    }
  }

  const loadContentQuality = async (id: number, priority = false) => {
    contentQualityLoading.value = true
    contentQualityError.value = ''
    try {
      const data = await loadContentQualityMutation.mutateAsync({ id, priority })
      contentQuality.value = data.quality ?? null
    } catch (err: unknown) {
      contentQualityError.value = errorMessage(err, 'Failed to load text quality')
    } finally {
      contentQualityLoading.value = false
    }
  }

  const loadOcrScores = async (id: number, refresh = false) => {
    ocrScoresLoading.value = true
    ocrScoresError.value = ''
    try {
      const data = await loadOcrScoresMutation.mutateAsync({ id, refresh })
      ocrScores.value = data.scores ?? []
    } catch (err: unknown) {
      ocrScoresError.value = errorMessage(err, 'Failed to load OCR scores')
    } finally {
      ocrScoresLoading.value = false
    }
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
    document,
    loading,
    syncing,
    tags,
    correspondents,
    docTypes,
    pageTexts,
    pageTextsVisionProgress,
    pageTextsLoading,
    pageTextsError,
    contentQuality,
    contentQualityLoading,
    contentQualityError,
    ocrScores,
    ocrScoresLoading,
    ocrScoresError,
    suggestions,
    suggestionsLoading,
    suggestionsError,
    suggestionVariants,
    suggestionVariantLoading,
    suggestionVariantError,
    loadDocument,
    loadMeta,
    loadPageTexts,
    loadContentQuality,
    loadOcrScores,
    loadSuggestions,
    refreshSuggestions,
    suggestField,
    applyVariant,
    applyToDocument,
  }
}
