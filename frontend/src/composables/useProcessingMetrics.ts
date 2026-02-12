import { computed, type ComputedRef } from 'vue'
import type { EmbedStatus, SyncStatus } from '../services/documents'
import type { QueueStatus } from '../services/queue'

const formatDuration = (totalSeconds: number) => {
  const safe = Math.max(0, Math.round(totalSeconds))
  const hours = Math.floor(safe / 3600)
  const minutes = Math.floor((safe % 3600) / 60)
  const seconds = safe % 60
  return `${hours}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`
}

const etaFromStatus = (status: { eta_seconds?: number | null; started_at?: string | null; processed?: number | null; total?: number | null }) => {
  if (status.eta_seconds !== null && status.eta_seconds !== undefined) {
    const minutes = Math.floor(status.eta_seconds / 60)
    const seconds = status.eta_seconds % 60
    return `${minutes}:${seconds.toString().padStart(2, '0')}`
  }
  if (!status.started_at || !status.processed) return '--'
  const started = Date.parse(status.started_at)
  if (Number.isNaN(started)) return '--'
  const elapsedMs = Date.now() - started
  const rate = status.processed / Math.max(1, elapsedMs / 1000)
  if (!status.total || rate <= 0) return '--'
  const remaining = status.total - status.processed
  return formatDuration(remaining / rate)
}

export const useProcessingMetrics = (
  syncStatus: ComputedRef<SyncStatus>,
  embedStatus: ComputedRef<EmbedStatus>,
  queueStatus: ComputedRef<QueueStatus>,
) => {
  const isProcessing = computed(
    () => syncStatus.value.status === 'running' || embedStatus.value.status === 'running',
  )
  const isSyncingNow = computed(() => syncStatus.value.status === 'running')
  const hasQueuedWork = computed(() => {
    if (!queueStatus.value.enabled) return false
    return (queueStatus.value.length ?? 0) > 0 || (queueStatus.value.in_progress ?? 0) > 0
  })
  const showCancel = computed(() => isProcessing.value || hasQueuedWork.value)
  const embedLabel = computed(() => {
    if (queueStatus.value.enabled && (queueStatus.value.length || queueStatus.value.in_progress)) {
      return 'Queue'
    }
    return 'Embed'
  })
  const progressPercent = computed(() => {
    if (!syncStatus.value.total) return 0
    return Math.min(100, Math.round((syncStatus.value.processed / syncStatus.value.total) * 100))
  })
  const etaText = computed(() => etaFromStatus(syncStatus.value))
  const queueOutstanding = computed(
    () => (queueStatus.value.length ?? 0) + (queueStatus.value.in_progress ?? 0),
  )
  const queueIsIdle = computed(() => !queueStatus.value.enabled || queueOutstanding.value === 0)
  const queueProcessed = computed(() => (queueIsIdle.value ? 0 : (queueStatus.value.done ?? 0)))
  const queueTotal = computed(() =>
    queueIsIdle.value
      ? 0
      : Math.max(queueStatus.value.total ?? 0, queueProcessed.value + queueOutstanding.value),
  )
  const queueEtaText = computed(() => {
    const lastRun = queueStatus.value.last_run_seconds ?? null
    if (!lastRun || !queueOutstanding.value) return '--'
    return formatDuration(lastRun * queueOutstanding.value)
  })
  const lastRunText = computed(() => {
    const lastRun = queueStatus.value.last_run_seconds ?? null
    if (!lastRun) return '--'
    return formatDuration(lastRun)
  })
  const processingProcessed = computed(() =>
    hasQueuedWork.value ? queueProcessed.value : embedStatus.value.processed,
  )
  const processingTotal = computed(() =>
    hasQueuedWork.value ? queueTotal.value : embedStatus.value.total,
  )
  const processingPercent = computed(() => {
    if (!processingTotal.value) return 0
    return Math.min(100, Math.round((processingProcessed.value / processingTotal.value) * 100))
  })
  const processingEtaText = computed(() =>
    hasQueuedWork.value ? queueEtaText.value : etaFromStatus(embedStatus.value),
  )

  return {
    isProcessing,
    isSyncingNow,
    hasQueuedWork,
    showCancel,
    embedLabel,
    progressPercent,
    etaText,
    lastRunText,
    processingProcessed,
    processingTotal,
    processingPercent,
    processingEtaText,
  }
}
