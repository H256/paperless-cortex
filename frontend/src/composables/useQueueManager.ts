import { computed, ref } from 'vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import {
  clearQueue,
  fetchQueuePeek,
  fetchQueueRunning,
  fetchQueueStatus,
  fetchQueueTaskRuns,
  moveQueueItem,
  moveQueueItemBottom,
  moveQueueItemTop,
  pauseQueue,
  removeQueueItem,
  resetQueueStats,
  resumeQueue,
} from '../services/queue'

export const useQueueManager = () => {
  const queryClient = useQueryClient()
  const peekLimit = ref(20)
  const taskRunsLimit = ref(50)
  const taskRunsDocId = ref('')
  const taskRunsTask = ref('')
  const taskRunsStatus = ref('')
  const taskRunsErrorType = ref('')

  const statusQuery = useQuery({
    queryKey: ['queue-status'],
    queryFn: () => fetchQueueStatus(),
    refetchInterval: 30_000,
    staleTime: 5_000,
  })

  const runningQuery = useQuery({
    queryKey: ['queue-running'],
    queryFn: () => fetchQueueRunning(),
    refetchInterval: 30_000,
    staleTime: 5_000,
  })

  const peekQuery = useQuery({
    queryKey: computed(() => ['queue-peek', peekLimit.value]),
    queryFn: () => fetchQueuePeek(peekLimit.value),
    refetchInterval: 30_000,
    staleTime: 5_000,
  })

  const taskRunsQuery = useQuery({
    queryKey: computed(() => [
      'queue-task-runs',
      taskRunsLimit.value,
      taskRunsDocId.value,
      taskRunsTask.value,
      taskRunsStatus.value,
      taskRunsErrorType.value,
    ]),
    queryFn: () =>
      fetchQueueTaskRuns({
        limit: taskRunsLimit.value,
        doc_id: taskRunsDocId.value ? Number(taskRunsDocId.value) : undefined,
        task: taskRunsTask.value || undefined,
        status: taskRunsStatus.value || undefined,
        error_type: taskRunsErrorType.value || undefined,
      }),
    staleTime: 5_000,
  })

  const invalidateQueue = async () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: ['queue-status'] }),
      queryClient.invalidateQueries({ queryKey: ['queue-running'] }),
      queryClient.invalidateQueries({ queryKey: ['queue-peek'] }),
    ])

  const clearMutation = useMutation({
    mutationFn: () => clearQueue(),
    onSuccess: invalidateQueue,
  })
  const resetStatsMutation = useMutation({
    mutationFn: () => resetQueueStats(),
    onSuccess: invalidateQueue,
  })
  const pauseMutation = useMutation({
    mutationFn: () => pauseQueue(),
    onSuccess: invalidateQueue,
  })
  const resumeMutation = useMutation({
    mutationFn: () => resumeQueue(),
    onSuccess: invalidateQueue,
  })
  const moveMutation = useMutation({
    mutationFn: ({ fromIndex, toIndex }: { fromIndex: number; toIndex: number }) =>
      moveQueueItem({ from_index: fromIndex, to_index: toIndex }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['queue-peek'] })
    },
  })
  const moveTopMutation = useMutation({
    mutationFn: (index: number) => moveQueueItemTop({ index }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['queue-peek'] })
    },
  })
  const moveBottomMutation = useMutation({
    mutationFn: (index: number) => moveQueueItemBottom({ index }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['queue-peek'] })
    },
  })
  const removeMutation = useMutation({
    mutationFn: (index: number) => removeQueueItem({ index }),
    onSuccess: invalidateQueue,
  })

  const loading = computed(
    () =>
      statusQuery.isPending.value ||
      runningQuery.isPending.value ||
      statusQuery.isFetching.value ||
      runningQuery.isFetching.value,
  )
  const peekLoading = computed(() => peekQuery.isPending.value || peekQuery.isFetching.value)
  const error = computed(() => {
    const err = peekQuery.error.value
    if (!err) return ''
    return err instanceof Error ? err.message : String(err)
  })

  const refresh = async () =>
    Promise.all([
      statusQuery.refetch(),
      runningQuery.refetch(),
      peekQuery.refetch(),
      taskRunsQuery.refetch(),
    ])

  const busy = computed(
    () =>
      clearMutation.isPending.value ||
      resetStatsMutation.isPending.value ||
      pauseMutation.isPending.value ||
      resumeMutation.isPending.value ||
      moveMutation.isPending.value ||
      moveTopMutation.isPending.value ||
      moveBottomMutation.isPending.value ||
      removeMutation.isPending.value,
  )

  return {
    status: computed(() => statusQuery.data.value ?? { enabled: false, length: null }),
    running: computed(() => runningQuery.data.value ?? { enabled: false, task: null, started_at: null }),
    peekItems: computed(() => peekQuery.data.value?.items ?? []),
    taskRuns: computed(() => taskRunsQuery.data.value?.items ?? []),
    taskRunsCount: computed(() => taskRunsQuery.data.value?.count ?? 0),
    taskRunsLoading: computed(() => taskRunsQuery.isPending.value || taskRunsQuery.isFetching.value),
    peekLimit,
    taskRunsLimit,
    taskRunsDocId,
    taskRunsTask,
    taskRunsStatus,
    taskRunsErrorType,
    loading,
    peekLoading,
    busy,
    error,
    refresh,
    loadPeek: async () => peekQuery.refetch(),
    loadTaskRuns: async () => taskRunsQuery.refetch(),
    clearQueue: () => clearMutation.mutateAsync(),
    resetStats: () => resetStatsMutation.mutateAsync(),
    pauseQueue: () => pauseMutation.mutateAsync(),
    resumeQueue: () => resumeMutation.mutateAsync(),
    moveItem: (fromIndex: number, toIndex: number) => moveMutation.mutateAsync({ fromIndex, toIndex }),
    moveTop: (index: number) => moveTopMutation.mutateAsync(index),
    moveBottom: (index: number) => moveBottomMutation.mutateAsync(index),
    removeItem: (index: number) => removeMutation.mutateAsync(index),
  }
}
