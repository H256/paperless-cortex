import { computed } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { fetchQueueTaskRuns } from '../services/queue'

export const useDocumentTaskRuns = (docId: () => number) => {
  const query = useQuery({
    queryKey: computed(() => ['document-task-runs', docId()]),
    queryFn: () =>
      fetchQueueTaskRuns({
        doc_id: docId(),
        limit: 30,
      }),
    enabled: computed(() => Number.isFinite(docId()) && docId() > 0),
    staleTime: 5_000,
  })

  return {
    taskRuns: computed(() => query.data.value?.items ?? []),
    taskRunsLoading: computed(() => query.isPending.value || query.isFetching.value),
    taskRunsError: computed(() => {
      const err = query.error.value
      if (!err) return ''
      return err instanceof Error ? err.message : String(err)
    }),
    refreshTaskRuns: () => query.refetch(),
  }
}
