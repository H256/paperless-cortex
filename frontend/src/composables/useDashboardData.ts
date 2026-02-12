import { computed } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { getDashboard } from '../services/documents'
import type { DocumentDashboard } from '../services/documents'

export const useDashboardData = () => {
  const query = useQuery({
    queryKey: ['dashboard-data'],
    queryFn: () => getDashboard(),
    staleTime: 60_000,
  })

  const loading = computed(() => query.isPending.value || query.isFetching.value)
  const error = computed(() => {
    const err = query.error.value
    if (!err) return ''
    return err instanceof Error ? err.message : String(err)
  })
  const data = computed<DocumentDashboard | null>(() => query.data.value ?? null)

  const refresh = async () => query.refetch()

  return {
    loading,
    error,
    data,
    refresh,
  }
}
