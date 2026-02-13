<template>
  <section>
    <div class="mb-4 flex items-center justify-between gap-3">
      <div>
        <h2 class="text-2xl font-semibold tracking-tight">Continue Processing</h2>
        <p class="text-sm text-slate-500">
          Review missing work, adjust strategy, and enqueue processing.
        </p>
      </div>
      <button
        class="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
        @click="goBack"
      >
        Back to Documents
      </button>
    </div>

    <ContinueProcessingPanel
      :sync-status="syncStatus"
      :progress-percent="progressPercent"
      :eta-text="etaText"
      :process-preview-loading="processPreviewLoading"
      :process-preview="processPreview"
      :process-options="processOptions"
      :batch-index="batchIndex"
      :batch-options="batchOptions"
      :batch-label="batchLabel"
      :process-start-result="processStartResult"
      :process-start-loading="processStartLoading"
      :syncing="syncing"
      :is-syncing-now="isSyncingNow"
      :queue-enabled="Boolean(queueStatus.enabled)"
      :queue-length="typeof queueStatus.length === 'number' ? queueStatus.length : null"
      :processing-active="isProcessing"
      @update:batch-index="batchIndex = $event"
      @close="goBack"
      @start="startFromPreview"
      @open-doc="openDoc"
      @open-queue="openQueue"
      @open-logs="openLogs"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ContinueProcessingPanel from '../components/ContinueProcessingPanel.vue'
import { useContinueProcessing } from '../composables/useContinueProcessing'
import { useContinueProcessOptions } from '../composables/useContinueProcessOptions'
import { usePreviewAutoRefresh } from '../composables/usePreviewAutoRefresh'
import { useProcessingOverview } from '../composables/useProcessingOverview'
import { useProcessingMetrics } from '../composables/useProcessingMetrics'
import { useToastStore } from '../stores/toastStore'

const router = useRouter()
const route = useRoute()
const toastStore = useToastStore()

const {
  syncStatus,
  embedStatus,
  queueStatus,
  refresh: refreshProcessingOverview,
} = useProcessingOverview()

const {
  processPreview,
  processPreviewLoading,
  processStartResult,
  processStartLoading,
  showPreviewModal,
  openPreview: openPreviewRequest,
  refreshProcessPreview,
  startFromPreview: startFromPreviewRequest,
  closePreview: clearPreviewState,
} = useContinueProcessing()

const { processOptions, batchOptions, batchIndex, batchLabel, processParams } =
  useContinueProcessOptions()

const {
  isProcessing,
  isSyncingNow,
  progressPercent,
  etaText,
} = useProcessingMetrics(syncStatus, embedStatus, queueStatus)

const syncing = computed(() => isProcessing.value)
const STRATEGIES = new Set(['balanced', 'paperless_only', 'vision_first', 'max_coverage'])

const parseBoolQuery = (value: unknown, fallback: boolean) => {
  const raw = Array.isArray(value) ? value[0] : value
  if (raw === '1' || raw === 'true') return true
  if (raw === '0' || raw === 'false') return false
  return fallback
}

const parseStrategyQuery = (value: unknown) => {
  const raw = String(Array.isArray(value) ? value[0] : value || '')
  return STRATEGIES.has(raw) ? (raw as typeof processOptions.strategy) : processOptions.strategy
}

const parseLimitQuery = (value: unknown) => {
  const raw = String(Array.isArray(value) ? value[0] : value || '')
  if (!raw || raw.toLowerCase() === 'all') return null
  const parsed = Number.parseInt(raw, 10)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null
}

const hydrateFromRouteQuery = () => {
  processOptions.includeSync = parseBoolQuery(route.query.sync, true)
  processOptions.strategy = parseStrategyQuery(route.query.strategy)
  const limit = parseLimitQuery(route.query.limit)
  const targetLabel = limit == null ? 'All' : String(limit)
  const idx = batchOptions.findIndex((entry) => String(entry) === targetLabel)
  if (idx >= 0) batchIndex.value = idx
}

const syncRouteQueryFromState = async () => {
  const nextQuery: Record<string, string> = {}
  const syncVal = processOptions.includeSync ? '1' : '0'
  if (syncVal !== '1') nextQuery.sync = syncVal
  if (processOptions.strategy !== 'balanced') nextQuery.strategy = processOptions.strategy
  const selectedBatch = batchOptions[batchIndex.value]
  if (selectedBatch !== 'All') nextQuery.limit = String(selectedBatch)

  const currentQuery: Record<string, string> = {}
  for (const [key, val] of Object.entries(route.query)) {
    const raw = Array.isArray(val) ? val[0] : val
    if (typeof raw === 'string' && raw) currentQuery[key] = raw
  }
  if (JSON.stringify(currentQuery) === JSON.stringify(nextQuery)) return
  await router.replace({ path: route.path, query: nextQuery })
}

const loadPreview = async () => {
  try {
    await openPreviewRequest(processParams())
    await refreshProcessingOverview()
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to load processing preview'
    toastStore.push(message, 'danger', 'Continue processing')
  }
}

const startFromPreview = async () => {
  try {
    await startFromPreviewRequest(processParams())
    await refreshProcessingOverview()
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to start processing'
    toastStore.push(message, 'danger', 'Continue processing')
  }
}

const goBack = () => {
  clearPreviewState()
  router.push('/documents')
}

const openDoc = (id: number) => {
  clearPreviewState()
  router.push(`/documents/${id}`)
}

const openQueue = () => {
  clearPreviewState()
  router.push('/queue')
}

const openLogs = () => {
  clearPreviewState()
  router.push('/logs')
}

onMounted(async () => {
  hydrateFromRouteQuery()
  await loadPreview()
})

watch(
  () => [processOptions.includeSync, processOptions.strategy, batchIndex.value],
  async () => {
    await syncRouteQueryFromState()
  },
)

usePreviewAutoRefresh(
  processOptions,
  batchIndex,
  showPreviewModal,
  processParams,
  refreshProcessPreview,
)
</script>
