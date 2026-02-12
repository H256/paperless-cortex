import { computed } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { fetchQueueTaskRuns } from '../services/queue'

const stageLabel = (stage: string) => {
  if (stage === 'vision_ocr') return 'Vision OCR'
  if (stage === 'embedding_chunks') return 'Embeddings'
  if (stage === 'page_notes') return 'Page notes'
  if (stage === 'summary_sections') return 'Hier summary'
  return stage
}

const checkpointLabel = (checkpoint?: Record<string, unknown> | null) => {
  if (!checkpoint || typeof checkpoint !== 'object') return 'Running'
  const stage = typeof checkpoint.stage === 'string' ? checkpoint.stage : 'progress'
  const current = typeof checkpoint.current === 'number' ? checkpoint.current : null
  const total = typeof checkpoint.total === 'number' ? checkpoint.total : null
  const label = stageLabel(stage)
  if (current != null && total != null && total > 0) return `${label} ${current}/${total}`
  return label
}

export const useRunningTaskProgress = () => {
  const runningQuery = useQuery({
    queryKey: ['queue-task-runs-running-docs'],
    queryFn: () =>
      fetchQueueTaskRuns({
        status: 'running',
        limit: 300,
      }),
    refetchInterval: 15_000,
    staleTime: 5_000,
  })

  const byDocId = computed<Record<number, string>>(() => {
    const map: Record<number, string> = {}
    const items = runningQuery.data.value?.items ?? []
    for (const run of items) {
      if (typeof run.doc_id !== 'number' || run.doc_id <= 0) continue
      if (map[run.doc_id]) continue
      map[run.doc_id] = checkpointLabel(run.checkpoint as Record<string, unknown> | null | undefined)
    }
    return map
  })

  return {
    runningByDocId: byDocId,
    runningLoading: computed(() => runningQuery.isPending.value || runningQuery.isFetching.value),
  }
}

