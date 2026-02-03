import { defineStore } from 'pinia'
import { searchEmbeddings, type SearchResult } from '../services/search'

export const useSearchStore = defineStore('search', {
  state: () => ({
    query: '',
    topK: 10,
    source: '',
    onlyVision: false,
    minQuality: 0,
    dedupe: true,
    rerank: true,
    results: [] as SearchResult[],
    loading: false,
    error: '',
  }),
  getters: {
    effectiveSource(state) {
      if (state.onlyVision) return 'vision_ocr'
      return state.source || ''
    },
    filteredResults(state): SearchResult[] {
      const source = state.onlyVision ? 'vision_ocr' : state.source || ''
      if (!source) return state.results
      return state.results.filter((result) => result.source === source)
    },
  },
  actions: {
    async runSearch() {
      if (!this.query) return
      this.loading = true
      this.error = ''
      try {
        const source = this.onlyVision ? 'vision_ocr' : this.source || undefined
        const data = await searchEmbeddings({
          q: this.query,
          top_k: this.topK,
          source,
          dedupe: this.dedupe,
          rerank: this.rerank,
          min_quality: this.minQuality || undefined,
        })
        this.results = data.matches ?? []
      } catch (err: unknown) {
        this.error = err instanceof Error ? err.message : 'Search failed'
      } finally {
        this.loading = false
      }
    },
  },
})
