import { computed, type Ref } from 'vue'
import { toTitle } from '../utils/documentDetail'

type ProcessingState = 'done' | 'missing' | 'na'

type ProcessingStatusItem = {
  label: string
  state: ProcessingState
  detail: string
}

type PipelineStep = {
  key: string
  required: boolean
  done: boolean
  detail?: string | null
}

type PipelineStatusLike = {
  steps?: PipelineStep[] | null
  preferred_source?: string | null
  is_large_document?: boolean | null
}

type PipelineFanoutLike = {
  items?: PipelineFanoutItemLike[] | null
}

type PipelineFanoutItemLike = {
  order?: number
  task?: string | null
  source?: string | null
  status?: string | null
  last_started_at?: string | null
  checkpoint?: unknown
  error_type?: string | null
}

type TimelineTaskRunLike = {
  task?: string | null
  status?: string | null
  checkpoint?: unknown
}

export const processingStateLabel = (state: ProcessingState) => {
  if (state === 'done') return 'Done'
  if (state === 'missing') return 'Missing'
  return 'N/A'
}

export const processingBadgeClass = (state: ProcessingState) => {
  if (state === 'done') return 'text-emerald-600 dark:text-emerald-300'
  if (state === 'missing') return 'text-amber-600 dark:text-amber-300'
  return 'text-slate-400 dark:text-slate-500'
}

export const fanoutStatusClass = (status: string | null | undefined) => {
  const normalized = String(status || '').toLowerCase()
  if (normalized === 'done') return 'text-emerald-700 dark:text-emerald-300 font-semibold'
  if (normalized === 'running' || normalized === 'retrying') return 'text-indigo-700 dark:text-indigo-300 font-semibold'
  if (normalized === 'failed') return 'text-rose-700 dark:text-rose-300 font-semibold'
  if (normalized === 'missing') return 'text-amber-700 dark:text-amber-300 font-semibold'
  return 'text-slate-600 dark:text-slate-300'
}

export const useDocumentProcessingState = (
  params: {
    pipelineStatus: Ref<PipelineStatusLike | null | undefined>
    pipelineFanout: Ref<PipelineFanoutLike | null | undefined>
    taskRuns: Ref<TimelineTaskRunLike[]>
    continueQueuedWaiting: Ref<boolean>
  },
  checkpointLabel: (checkpoint?: Record<string, unknown> | null) => string,
) => {
  const processingStatusItems = computed<ProcessingStatusItem[]>(() => {
    if (!params.pipelineStatus.value?.steps?.length) return []
    return params.pipelineStatus.value.steps.map((step) => ({
      label: toTitle(step.key),
      state: step.required ? (step.done ? 'done' : 'missing') : 'na',
      detail: step.detail || '',
    }))
  })

  const processingRequiredCount = computed(
    () => processingStatusItems.value.filter((item) => item.state !== 'na').length,
  )

  const processingDoneCount = computed(
    () => processingStatusItems.value.filter((item) => item.state === 'done').length,
  )

  const pipelineFanoutItems = computed<PipelineFanoutItemLike[]>(
    () => params.pipelineFanout.value?.items || [],
  )

  const activeRun = computed(() =>
    params.taskRuns.value.find((run) => run.status === 'running' || run.status === 'retrying') ?? null,
  )

  const hasActiveTaskRuns = computed(() =>
    params.taskRuns.value.some((run) => run.status === 'running' || run.status === 'retrying'),
  )

  const activeRunLabel = computed(() => {
    const run = activeRun.value
    if (!run || !run.task) return ''
    const stage = checkpointLabel(
      run.checkpoint && typeof run.checkpoint === 'object'
        ? (run.checkpoint as Record<string, unknown>)
        : null,
    )
    return stage !== '-' ? `${run.task} (${stage})` : run.task
  })

  const shouldAutoRefreshTimeline = computed(
    () => hasActiveTaskRuns.value || params.continueQueuedWaiting.value,
  )

  const pipelinePreferredSource = computed(
    () => params.pipelineStatus.value?.preferred_source || 'paperless_ocr',
  )

  const isLargeDocumentMode = computed(() => Boolean(params.pipelineStatus.value?.is_large_document))

  const largeDocumentHint = computed(() => {
    if (isLargeDocumentMode.value) {
      return 'Large-document mode active: page notes and hierarchical summary are required for complete processing.'
    }
    return 'Standard mode: large-document extras are not required for this document.'
  })

  return {
    processingStatusItems,
    processingRequiredCount,
    processingDoneCount,
    pipelineFanoutItems,
    activeRun,
    hasActiveTaskRuns,
    activeRunLabel,
    shouldAutoRefreshTimeline,
    pipelinePreferredSource,
    isLargeDocumentMode,
    largeDocumentHint,
  }
}
