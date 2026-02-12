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
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import ContinueProcessingPanel from '../components/ContinueProcessingPanel.vue'
import { useContinueProcessing } from '../composables/useContinueProcessing'
import { useContinueProcessOptions } from '../composables/useContinueProcessOptions'
import { usePreviewAutoRefresh } from '../composables/usePreviewAutoRefresh'
import { useProcessingOverview } from '../composables/useProcessingOverview'
import { useProcessingMetrics } from '../composables/useProcessingMetrics'
import { useToastStore } from '../stores/toastStore'

const router = useRouter()
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
  await loadPreview()
})

usePreviewAutoRefresh(
  processOptions,
  batchIndex,
  showPreviewModal,
  processParams,
  refreshProcessPreview,
)
</script>
