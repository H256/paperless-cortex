import { computed, ref } from 'vue'
import { useMutation } from '@tanstack/vue-query'
import { searchEmbeddings, type SearchResult } from '../services/search'

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
  const error = ref('')

  const effectiveSource = computed(() => (onlyVision.value ? 'vision_ocr' : source.value || ''))
  const filteredResults = computed(() => {
    if (!effectiveSource.value) return results.value
    return results.value.filter((result) => result.source === effectiveSource.value)
  })

  const runMutation = useMutation({
    mutationFn: async () => {
      if (!query.value.trim()) return []
      const data = await searchEmbeddings({
        q: query.value,
        top_k: topK.value,
        source: effectiveSource.value || undefined,
        dedupe: dedupe.value,
        rerank: rerank.value,
        min_quality: minQuality.value || undefined,
      })
      return data.matches ?? []
    },
    onMutate: () => {
      error.value = ''
    },
    onSuccess: (matches) => {
      results.value = matches
    },
    onError: (err) => {
      error.value = errorMessage(err, 'Search failed')
    },
  })

  return {
    query,
    topK,
    source,
    onlyVision,
    minQuality,
    dedupe,
    rerank,
    results,
    filteredResults,
    loading: computed(() => runMutation.isPending.value),
    error,
    runSearch: async () => runMutation.mutateAsync(),
  }
}

