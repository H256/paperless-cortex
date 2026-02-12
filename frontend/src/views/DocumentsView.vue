<template>
  <section>
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-2xl font-semibold tracking-tight">Documents</h2>
        <p class="text-sm text-slate-500">
          Manage ingestion, embedding, and review analysis status.
        </p>
      </div>
      <DocumentsOverviewPanel
        :stats="stats"
        :queued-count="queueStatus.enabled ? (queueStatus.length ?? 0) : 0"
        :is-processing="isProcessing"
        :sync-status="syncStatus"
        :embed-status="embedStatus"
        :has-queued-work="hasQueuedWork"
        :progress-percent="progressPercent"
        :eta-text="etaText"
        :embed-label="embedLabel"
        :processing-processed="processingProcessed"
        :processing-total="processingTotal"
        :processing-percent="processingPercent"
        :processing-eta-text="processingEtaText"
        :last-run-text="lastRunText"
      />
    </div>

    <DocumentsProcessingToolbar
      :continue-processing-running="continueProcessingRunning"
      :processing-kickoff-pending="processingKickoffPending"
      :is-processing="isProcessing"
      :show-cancel="showCancel"
      @open-preview="openPreview"
      @cancel-processing="cancelProcessing"
    />
    <div
      v-if="processingKickoffPending"
      class="mt-3 rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-2 text-xs text-indigo-700 dark:border-indigo-900/50 dark:bg-indigo-950/30 dark:text-indigo-200"
    >
      Starting processing and enqueueing missing tasks...
    </div>

    <DocumentsFiltersPanel
      :tags="tags"
      :correspondents="correspondents"
      v-model:ordering="ordering"
      v-model:selected-correspondent="selectedCorrespondent"
      v-model:selected-tag="selectedTag"
      v-model:date-from="dateFrom"
      v-model:date-to="dateTo"
      v-model:analysis-filter="analysisFilter"
      v-model:selected-review-status="selectedReviewStatus"
      v-model:model-filter="modelFilter"
      v-model:page-size="pageSize"
      @reload="load"
    />

    <DocumentsTable
      :documents="visibleDocuments"
      :running-by-doc-id="runningByDocId"
      :ordering="ordering"
      :correspondents="correspondents"
      :paperless-base-url="paperlessBaseUrl"
      :page="page"
      :total-pages="totalPages"
      :last-synced="lastSynced"
      @toggle-sort="toggleSort"
      @open-doc="open"
      @prev-page="onPrevPage"
      @next-page="onNextPage"
    />
  </section>

  <ContinueProcessingModal
    :open="showPreviewModal"
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
    @close="closePreview"
    @start="startFromPreview"
    @open-doc="openDocFromPreview"
    @open-queue="openQueueFromPreview"
    @open-logs="openLogsFromPreview"
  />
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useToastStore } from '../stores/toastStore'
import { useContinueProcessing } from '../composables/useContinueProcessing'
import { useContinueProcessOptions } from '../composables/useContinueProcessOptions'
import { useDocumentsCatalog } from '../composables/useDocumentsCatalog'
import { useDocumentsProcessingActions } from '../composables/useDocumentsProcessingActions'
import { useDocumentsTableControls } from '../composables/useDocumentsTableControls'
import { useProcessingOverview } from '../composables/useProcessingOverview'
import { useProcessingMetrics } from '../composables/useProcessingMetrics'
import { usePaperlessBaseUrl } from '../composables/usePaperlessBaseUrl'
import { usePreviewAutoRefresh } from '../composables/usePreviewAutoRefresh'
import { useVisibleDocuments } from '../composables/useVisibleDocuments'
import { useRunningTaskProgress } from '../composables/useRunningTaskProgress'
import ContinueProcessingModal from '../components/ContinueProcessingModal.vue'
import DocumentsFiltersPanel from '../components/DocumentsFiltersPanel.vue'
import DocumentsOverviewPanel from '../components/DocumentsOverviewPanel.vue'
import DocumentsProcessingToolbar from '../components/DocumentsProcessingToolbar.vue'
import DocumentsTable from '../components/DocumentsTable.vue'

const router = useRouter()
const toastStore = useToastStore()
const {
  documents,
  page,
  pageSize,
  ordering,
  totalCount,
  tags,
  correspondents,
  selectedTag,
  selectedCorrespondent,
  selectedReviewStatus,
  dateFrom,
  dateTo,
  refetchDocuments,
} = useDocumentsCatalog()
const {
  syncStatus,
  embedStatus,
  stats,
  queueStatus,
  lastSynced,
  refresh: refreshProcessingOverview,
  clearQueueNow,
} = useProcessingOverview()
const { paperlessBaseUrl } = usePaperlessBaseUrl()
const {
  processPreview,
  processPreviewLoading,
  processStartResult,
  processStartLoading,
  showPreviewModal,
  continueProcessingRunning,
  openPreview: openPreviewRequest,
  refreshProcessPreview,
  startFromPreview: startFromPreviewRequest,
  cancelProcessing: cancelProcessingRequest,
  closePreview: clearPreviewState,
} = useContinueProcessing()
const analysisFilter = ref<'all' | 'analyzed' | 'not_analyzed'>('all')
const modelFilter = ref('')
const { processOptions, batchOptions, batchIndex, batchLabel, processParams } =
  useContinueProcessOptions()
const { visibleDocuments } = useVisibleDocuments(documents, analysisFilter, modelFilter)
const { runningByDocId } = useRunningTaskProgress()

const totalPages = computed(() => Math.max(1, Math.ceil(totalCount.value / pageSize.value)))
const {
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
} = useProcessingMetrics(syncStatus, embedStatus, queueStatus)
const syncing = computed(() => isProcessing.value)

const load = async () => {
  try {
    await refetchDocuments()
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to load documents'
    toastStore.push(message, 'danger', 'Error')
  }
}
const { openPreview, closePreview, startFromPreview, cancelProcessing, processingKickoffPending } = useDocumentsProcessingActions(
  toastStore,
  {
    processStartResult,
    openPreviewRequest,
    startFromPreviewRequest,
    cancelProcessingRequest,
    clearPreviewState,
  },
  {
    refreshProcessingOverview,
    clearQueueNow,
  },
  load,
  processParams,
)
const { toggleSort, onPrevPage, onNextPage } = useDocumentsTableControls(
  ordering,
  page,
  totalPages,
  load,
)

const open = (id: number) => {
  router.push(`/documents/${id}`)
}

const openDocFromPreview = (id: number) => {
  closePreview()
  router.push(`/documents/${id}`)
}

const openQueueFromPreview = () => {
  closePreview()
  router.push('/queue')
}

const openLogsFromPreview = () => {
  closePreview()
  router.push('/logs')
}

onMounted(async () => {
  await load()
})
usePreviewAutoRefresh(
  processOptions,
  batchIndex,
  showPreviewModal,
  processParams,
  refreshProcessPreview,
)

</script>
