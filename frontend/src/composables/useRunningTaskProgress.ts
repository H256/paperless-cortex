import { computed, type Ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { fetchQueueTaskRuns } from '../services/queue'
import { formatCheckpointLabel, hasResumeMarker } from '../utils/taskRunCheckpoint'
import { taskLabel, type RunningTask } from '../utils/taskLabels'

export const useRunningTaskProgress = (options: { enabled?: Ref<boolean> } = {}) => {
  const runningQuery = useQuery({
    enabled: options.enabled ?? true,
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

  // What runs right now, for the status pill ("Vision OCR 3/12 · #2210").
  const runningTasks = computed<RunningTask[]>(() => {
    const items = runningQuery.data.value?.items ?? []
    const tasks: RunningTask[] = []
    for (const run of items) {
      const status = String(run.status || '').toLowerCase()
      if (status !== 'running' && status !== 'retrying') continue
      const checkpoint = run.checkpoint as Record<string, unknown> | null | undefined
      const hasProgress = Boolean(checkpoint && (checkpoint.stage || hasResumeMarker(checkpoint)))
      tasks.push({
        docId: typeof run.doc_id === 'number' && run.doc_id > 0 ? run.doc_id : null,
        label: hasProgress ? formatCheckpointLabel(checkpoint, taskLabel(run.task)) : taskLabel(run.task),
      })
    }
    return tasks
  })

  return {
    runningTasks,
    runningByDocId: byDocId,
    runningLoading: computed(() => runningQuery.isPending.value || runningQuery.isFetching.value),
  }
}
