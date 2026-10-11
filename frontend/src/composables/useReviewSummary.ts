import { computed } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { getReviewSummary } from '../services/documents'
import type { ReviewSummary } from '../services/documents'

export const useReviewSummary = () => {
  const query = useQuery({
    queryKey: ['review-summary'],
    queryFn: () => getReviewSummary(),
    staleTime: 30_000,
  })

  const loading = computed(() => query.isPending.value || query.isFetching.value)
  const error = computed(() => {
    const err = query.error.value
    if (!err) return ''
    return err instanceof Error ? err.message : String(err)
  })
  const summary = computed<ReviewSummary | null>(() => query.data.value ?? null)
  const refresh = async () => query.refetch()

  return { loading, error, summary, refresh }
}
