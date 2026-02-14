import { computed, ref } from 'vue'
import { useMutation } from '@tanstack/vue-query'
import { unwrap } from '../api/orval'
import { searchEmbeddingsSearchGet } from '../api/generated/client'
import type { EmbeddingMatch, EmbeddingSearchResponse } from '../api/generated/model'

export type SearchResult = EmbeddingMatch

const errorMessage = (err: unknown, fallback: string) => {
  if (err instanceof Error) return err.message || fallback
  if (typeof err === 'string') return err || fallback
  return fallback
}

export const useSearchSession = () => {
  const query = ref('')
  const topK = ref(10)
  const source = ref('')
  const onlyVision = ref(false)
  const minQuality = ref(0)
  const dedupe = ref(true)
  const rerank = ref(true)
  const results = ref<SearchResult[]>([])
  const hasSearched = ref(false)
  const error = ref('')

  const effectiveSource = computed(() => (onlyVision.value ? 'vision_ocr' : source.value || ''))
  const filteredResults = computed(() => {
    if (!effectiveSource.value) return results.value
    return results.value.filter((result) => result.source === effectiveSource.value)
  })

  const runMutation = useMutation({
    mutationFn: async () => {
      if (!query.value.trim()) return []
      const data = await unwrap<EmbeddingSearchResponse>(
        searchEmbeddingsSearchGet({
          q: query.value,
          top_k: topK.value,
          source: effectiveSource.value || undefined,
          dedupe: dedupe.value,
          rerank: rerank.value,
          min_quality: minQuality.value || undefined,
        }),
      )
      return data.matches ?? []
    },
    onMutate: () => {
      error.value = ''
    },
    onSuccess: (matches) => {
      results.value = matches
      hasSearched.value = true
    },
    onError: (err) => {
      error.value = errorMessage(err, 'Search failed')
    },
  })

  const resetSession = () => {
    query.value = ''
    topK.value = 10
    source.value = ''
    onlyVision.value = false
    minQuality.value = 0
    dedupe.value = true
    rerank.value = true
    results.value = []
    hasSearched.value = false
    error.value = ''
  }

  return {
    query,
    topK,
    source,
    onlyVision,
    minQuality,
    dedupe,
    rerank,
    results,
    hasSearched,
    filteredResults,
    loading: computed(() => runMutation.isPending.value),
    error,
    runSearch: async () => runMutation.mutateAsync(),
    resetSession,
  }
}
