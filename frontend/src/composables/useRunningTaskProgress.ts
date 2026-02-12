import { computed } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { fetchQueueTaskRuns } from '../services/queue'
import { formatCheckpointLabel } from '../utils/taskRunCheckpoint'

export const useRunningTaskProgress = () => {
  const runningQuery = useQuery({
    queryKey: ['queue-task-runs-running-docs'],
    queryFn: () =>
      fetchQueueTaskRuns({
        limit: 500,
      }),
    refetchInterval: 15_000,
    staleTime: 5_000,
  })

  const byDocId = computed<Record<number, string>>(() => {
    const map: Record<number, string> = {}
    const items = runningQuery.data.value?.items ?? []
    for (const run of items) {
      const status = String(run.status || '').toLowerCase()
      if (status !== 'running' && status !== 'retrying') continue
      if (typeof run.doc_id !== 'number' || run.doc_id <= 0) continue
      if (map[run.doc_id]) continue
      map[run.doc_id] = formatCheckpointLabel(
        run.checkpoint as Record<string, unknown> | null | undefined,
        'Running',
      )
    }
    return map
  })

  return {
    runningByDocId: byDocId,
    runningLoading: computed(() => runningQuery.isPending.value || runningQuery.isFetching.value),
  }
}
