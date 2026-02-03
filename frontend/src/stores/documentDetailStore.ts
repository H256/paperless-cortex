import { defineStore } from 'pinia'
import {
  type DocumentDetail,
  type DocumentType,
  type PageText,
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
  suggestFieldVariants,
  syncDocument,
} from '../services/documents'
import type {TextQualityMetrics} from "@/api/generated/model";

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

export const useDocumentDetailStore = defineStore('documentDetail', {
  state: () => ({
    document: null as DocumentDetail | null,
    loading: false,
    syncing: false,
    tags: [] as Tag[],
    correspondents: [] as Correspondent[],
    docTypes: [] as DocumentType[],
    pageTexts: [] as PageText[],
    pageTextsLoading: false,
    pageTextsError: '',
    contentQuality: null as TextQualityMetrics | null,
    contentQualityLoading: false,
    contentQualityError: '',
    suggestions: null as SuggestionsState | null,
    suggestionsLoading: false,
    suggestionsError: '',
    suggestionVariants: {} as Record<string, unknown[]>,
    suggestionVariantLoading: {} as Record<string, boolean>,
    suggestionVariantError: {} as Record<string, string>,
  }),
  actions: {
    async loadDocument(id: number) {
      this.loading = true
      try {
        const data = await getDocumentLocal(id)
        if (data?.status === 'missing') {
          this.document = null
        } else {
          this.document = data
        }
        this.pageTexts = []
        this.pageTextsError = ''
        this.contentQuality = null
        this.contentQualityError = ''
        this.suggestions = null
        this.suggestionsError = ''
        this.suggestionVariants = {}
        this.suggestionVariantLoading = {}
        this.suggestionVariantError = {}
      } finally {
        this.loading = false
      }
    },
    async resync(id: number, doReembed: boolean) {
      this.syncing = true
      try {
        await syncDocument(id, { embed: doReembed, force_embed: doReembed, priority: true })
        await this.loadDocument(id)
      } finally {
        this.syncing = false
      }
    },
    async loadMeta() {
      const [tagsResp, corrResp] = await Promise.all([getTags(), getCorrespondents()])
      this.tags = tagsResp.results ?? []
      this.correspondents = corrResp.results ?? []
      if (this.document?.document_type) {
        const docType = await getDocumentType(this.document.document_type)
        this.docTypes = [docType]
      }
    },
    async loadPageTexts(id: number, priority = false) {
      this.pageTextsLoading = true
      this.pageTextsError = ''
      try {
        const data = await getPageTexts(id, priority)
        this.pageTexts = data.pages ?? []
      } catch (err: unknown) {
        this.pageTextsError = errorMessage(err, 'Failed to load page texts')
      } finally {
        this.pageTextsLoading = false
      }
    },
    async loadContentQuality(id: number, priority = false) {
      this.contentQualityLoading = true
      this.contentQualityError = ''
      try {
        const data = await getTextQuality(id, priority)
        this.contentQuality = data.quality ?? null
      } catch (err: unknown) {
        this.contentQualityError = errorMessage(err, 'Failed to load text quality')
      } finally {
        this.contentQualityLoading = false
      }
    },
    async loadSuggestions(id: number) {
      this.suggestionsLoading = true
      this.suggestionsError = ''
      try {
        const data = await getSuggestions(id)
        const meta = (data as { suggestions_meta?: Record<string, unknown> }).suggestions_meta
        this.suggestions = data.suggestions
          ? { ...data.suggestions, suggestions_meta: meta }
          : null
      } catch (err: unknown) {
        this.suggestionsError = errorMessage(err, 'Failed to load suggestions')
      } finally {
        this.suggestionsLoading = false
      }
    },
    async refreshSuggestions(id: number, source: 'paperless_ocr' | 'vision_ocr') {
      this.suggestionsLoading = true
      this.suggestionsError = ''
      try {
        const data = await getSuggestions(id, { source, refresh: true, priority: true })
        const meta = (data as { suggestions_meta?: Record<string, unknown> }).suggestions_meta
        this.suggestions = data.suggestions
          ? { ...data.suggestions, suggestions_meta: meta }
          : null
      } catch (err: unknown) {
        this.suggestionsError = errorMessage(err, 'Failed to refresh suggestions')
      } finally {
        this.suggestionsLoading = false
      }
    },
    async suggestField(id: number, source: 'paperless_ocr' | 'vision_ocr', field: string) {
      const key = `${source}:${field}`
      this.suggestionVariantLoading = { ...this.suggestionVariantLoading, [key]: true }
      this.suggestionVariantError = { ...this.suggestionVariantError, [key]: '' }
      try {
        const data = await suggestFieldVariants(id, { source, field, count: 3 }, true)
        const variants = extractVariants(data)
        if (variants.length) {
          this.suggestionVariants = { ...this.suggestionVariants, [key]: variants }
        } else if (isQueued(data)) {
          await this.pollVariants(id, source, field)
        }
      } catch (err: unknown) {
        this.suggestionVariantError = {
          ...this.suggestionVariantError,
          [key]: errorMessage(err, 'Failed to generate variants'),
        }
      } finally {
        this.suggestionVariantLoading = { ...this.suggestionVariantLoading, [key]: false }
      }
    },
    async pollVariants(id: number, source: 'paperless_ocr' | 'vision_ocr', field: string) {
      const key = `${source}:${field}`
      for (let attempt = 0; attempt < 10; attempt += 1) {
        await new Promise((resolve) => setTimeout(resolve, 1200))
        try {
          const data = await fetchFieldVariants(id, source, field)
          if (Array.isArray(data.variants) && data.variants.length) {
            this.suggestionVariants = { ...this.suggestionVariants, [key]: data.variants }
            return
          }
        } catch (err: unknown) {
          this.suggestionVariantError = {
            ...this.suggestionVariantError,
            [key]: errorMessage(err, 'Failed to fetch variants'),
          }
          return
        }
      }
    },
    async applyVariant(
      id: number,
      source: 'paperless_ocr' | 'vision_ocr',
      field: string,
      value: unknown,
    ) {
      this.suggestionsLoading = true
      this.suggestionsError = ''
      try {
        const data = await applyFieldSuggestion(id, { source, field, value })
        const suggestions = (data as { suggestions?: SuggestionsState }).suggestions
        if (suggestions) {
          this.suggestions = { ...this.suggestions, ...suggestions }
        }
      } catch (err: unknown) {
        this.suggestionsError = errorMessage(err, 'Failed to apply suggestion')
      } finally {
        this.suggestionsLoading = false
      }
    },
    async applyToDocument(id: number, payload: { source?: string; field: string; value: unknown }) {
      await applySuggestionToDocument(id, payload)
    },
  },
})
