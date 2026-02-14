import { computed, ref, watch } from 'vue'
import { keepPreviousData, useQuery } from '@tanstack/vue-query'
import { fetchQueueTaskRuns, type QueueTaskRun } from '../services/queue'

type TaskRunPreset = {
  id: string
  name: string
  docId: string
  task: string
  status: string
  errorType: string
  limit: number
  offset: number
}

const PRESETS_STORAGE_KEY = 'task_run_inspector_presets_v1'

const loadPresets = (): TaskRunPreset[] => {
  try {
    const raw = window.localStorage.getItem(PRESETS_STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) return []
    return parsed
      .map((item) => item as Partial<TaskRunPreset>)
      .filter((item) => typeof item?.id === 'string' && typeof item?.name === 'string')
      .map((item) => ({
        id: String(item.id),
        name: String(item.name),
        docId: String(item.docId || ''),
        task: String(item.task || ''),
        status: String(item.status || ''),
        errorType: String(item.errorType || ''),
        limit: Number(item.limit || 100),
        offset: Number(item.offset || 0),
      }))
  } catch {
    return []
  }
}

const persistPresets = (presets: TaskRunPreset[]) => {
  window.localStorage.setItem(PRESETS_STORAGE_KEY, JSON.stringify(presets))
}

export const useTaskRunInspector = () => {
  const docId = ref('')
  const task = ref('')
  const status = ref('')
  const errorType = ref('')
  const limit = ref(100)
  const offset = ref(0)
  const autoRefresh = ref(true)

  watch([docId, task, status, errorType], () => {
    offset.value = 0
  })

  const presets = ref<TaskRunPreset[]>(loadPresets())
  watch(
    presets,
    (value) => {
      persistPresets(value)
    },
    { deep: true },
  )

  const taskRunsQuery = useQuery({
    queryKey: computed(() => [
      'task-run-inspector',
      docId.value,
      task.value,
      status.value,
      errorType.value,
      limit.value,
      offset.value,
    ]),
    queryFn: () =>
      fetchQueueTaskRuns({
        doc_id: docId.value ? Number(docId.value) : undefined,
        task: task.value || undefined,
        status: status.value || undefined,
        error_type: errorType.value || undefined,
        limit: limit.value,
        offset: offset.value,
      }),
    placeholderData: keepPreviousData,
    staleTime: 5_000,
    refetchInterval: computed(() => (autoRefresh.value ? 5_000 : false)),
  })

  const savePreset = (name: string) => {
    const trimmed = name.trim()
    if (!trimmed) return false
    const preset: TaskRunPreset = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      name: trimmed,
      docId: docId.value,
      task: task.value,
      status: status.value,
      errorType: errorType.value,
      limit: limit.value,
      offset: offset.value,
    }
    presets.value = [preset, ...presets.value].slice(0, 20)
    return true
  }

  const applyPreset = (presetId: string) => {
    const preset = presets.value.find((item) => item.id === presetId)
    if (!preset) return false
    docId.value = preset.docId
    task.value = preset.task
    status.value = preset.status
    errorType.value = preset.errorType
    limit.value = preset.limit
    return true
  }

  const deletePreset = (presetId: string) => {
    presets.value = presets.value.filter((item) => item.id !== presetId)
  }

  const clearFilters = () => {
    docId.value = ''
    task.value = ''
    status.value = ''
    errorType.value = ''
    limit.value = 100
    offset.value = 0
  }

  const nextPage = () => {
    if (!taskRunsQuery.data.value?.count) return
    const total = Number(taskRunsQuery.data.value.count || 0)
    const next = offset.value + limit.value
    if (next >= total) return
    offset.value = next
  }

  const prevPage = () => {
    offset.value = Math.max(0, offset.value - limit.value)
  }

  return {
    filters: {
      docId,
      task,
      status,
      errorType,
      limit,
      offset,
      autoRefresh,
    },
    taskRuns: computed<QueueTaskRun[]>(() => taskRunsQuery.data.value?.items ?? []),
    taskRunsCount: computed(() => taskRunsQuery.data.value?.count ?? 0),
    loading: computed(() => taskRunsQuery.isPending.value || taskRunsQuery.isFetching.value),
    error: computed(() => {
      const err = taskRunsQuery.error.value
      if (!err) return ''
      return err instanceof Error ? err.message : String(err)
    }),
    refresh: () => taskRunsQuery.refetch(),
    presets,
    savePreset,
    applyPreset,
    deletePreset,
    clearFilters,
    nextPage,
    prevPage,
  }
}
