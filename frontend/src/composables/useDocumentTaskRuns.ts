import { computed, type Ref } from 'vue'
import { keepPreviousData, useQuery } from '@tanstack/vue-query'
import { fetchQueueTaskRuns } from '../services/queue'

type DocumentTaskRunFilters = {
  limit?: Ref<number>
  task?: Ref<string>
  status?: Ref<string>
  errorType?: Ref<string>
  query?: Ref<string>
}

export const useDocumentTaskRuns = (docId: () => number, filters?: DocumentTaskRunFilters) => {
  const limitRef = filters?.limit
  const taskRef = filters?.task
  const statusRef = filters?.status
  const errorTypeRef = filters?.errorType
  const queryRef = filters?.query

  const query = useQuery({
    queryKey: computed(() => [
      'document-task-runs',
      docId(),
      limitRef?.value ?? 30,
      taskRef?.value ?? '',
      statusRef?.value ?? '',
      errorTypeRef?.value ?? '',
      queryRef?.value ?? '',
    ]),
    queryFn: () =>
      fetchQueueTaskRuns({
        doc_id: docId(),
        limit: limitRef?.value ?? 30,
        task: taskRef?.value || undefined,
        status: statusRef?.value || undefined,
        error_type: errorTypeRef?.value || undefined,
        q: queryRef?.value || undefined,
      }),
    placeholderData: keepPreviousData,
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
