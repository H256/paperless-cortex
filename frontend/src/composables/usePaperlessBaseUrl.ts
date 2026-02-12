import { computed } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { fetchHealthStatus } from '../services/status'

export const usePaperlessBaseUrl = () => {
  const runtimeQuery = useQuery({
    queryKey: ['runtime-status'],
    queryFn: () => fetchHealthStatus(),
    staleTime: 60_000,
  })

  const paperlessBaseUrl = computed(() => {
    const envUrl = import.meta.env.VITE_PAPERLESS_BASE_URL || ''
    if (envUrl) return envUrl
    return runtimeQuery.data.value?.paperless_base_url || ''
  })

  return { paperlessBaseUrl }
}
