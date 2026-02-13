<template>
  <section>
    <div class="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
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
      :continue-processing-running="false"
      :processing-kickoff-pending="false"
      :is-processing="isProcessing"
      :show-cancel="showCancel"
      @open-preview="openPreview"
      @cancel-processing="cancelProcessing"
      @open-queue="openQueue"
      @open-logs="openLogs"
    />

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

    <DocumentsQuickControls
      :selected-review-status="selectedReviewStatus"
      :view-mode="listViewMode"
      @update:selectedReviewStatus="setReviewQuickFilter"
      @update:viewMode="setListViewMode"
      @reset-quick-filters="resetQuickFilters"
      @open-writeback="openWritebackQueue"
      @open-processing="openPreview"
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
      :view-mode="listViewMode"
      @toggle-sort="toggleSort"
      @open-doc="open"
      @open-doc-operations="openOperations"
      @prev-page="onPrevPage"
      @next-page="onNextPage"
    />
  </section>

</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useToastStore } from '../stores/toastStore'
import { useDocumentsCatalog } from '../composables/useDocumentsCatalog'
import { useDocumentsTableControls } from '../composables/useDocumentsTableControls'
import { useProcessingOverview } from '../composables/useProcessingOverview'
import { useProcessingMetrics } from '../composables/useProcessingMetrics'
import { usePaperlessBaseUrl } from '../composables/usePaperlessBaseUrl'
import { useVisibleDocuments } from '../composables/useVisibleDocuments'
import { useRunningTaskProgress } from '../composables/useRunningTaskProgress'
import { useDocumentsRouteState } from '../composables/useDocumentsRouteState'
import DocumentsFiltersPanel from '../components/DocumentsFiltersPanel.vue'
import DocumentsQuickControls from '../components/DocumentsQuickControls.vue'
import DocumentsOverviewPanel from '../components/DocumentsOverviewPanel.vue'
import DocumentsProcessingToolbar from '../components/DocumentsProcessingToolbar.vue'
import DocumentsTable from '../components/DocumentsTable.vue'

const router = useRouter()
const route = useRoute()
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
  cancelSyncAndEmbeddings,
} = useProcessingOverview()
const { paperlessBaseUrl } = usePaperlessBaseUrl()
const analysisFilter = ref<'all' | 'analyzed' | 'not_analyzed'>('all')
const modelFilter = ref('')
const listViewMode = ref<'table' | 'cards'>('table')
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

const load = async () => {
  try {
    await refetchDocuments()
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to load documents'
    toastStore.push(message, 'danger', 'Error')
  }
}
const openPreview = async () => {
  await router.push('/processing/continue')
}
const openQueue = async () => {
  await router.push('/queue')
}
const openLogs = async () => {
  await router.push('/logs')
}
const openWritebackQueue = async () => {
  await router.push('/writeback')
}
const cancelProcessing = async () => {
  try {
    await cancelSyncAndEmbeddings()
    await clearQueueNow()
    await Promise.all([refreshProcessingOverview(), load()])
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to cancel processing'
    toastStore.push(message, 'danger', 'Processing')
  }
}
const { toggleSort, onPrevPage, onNextPage } = useDocumentsTableControls(
  ordering,
  page,
  totalPages,
  load,
)

const open = (id: number) => {
  router.push({
    path: `/documents/${id}`,
    query: { return_to: encodeURIComponent(route.fullPath) },
  })
}

const openOperations = (id: number) => {
  router.push({
    path: `/documents/${id}`,
    query: {
      return_to: encodeURIComponent(route.fullPath),
      tab: 'operations',
    },
  })
}

const hasExplicitViewQuery = computed(() => {
  const value = route.query.view
  const normalized = Array.isArray(value) ? value[0] : value
  return normalized === 'cards' || normalized === 'table'
})

const setReviewQuickFilter = (value: 'all' | 'unreviewed' | 'reviewed' | 'needs_review') => {
  selectedReviewStatus.value = value
  page.value = 1
}

const setListViewMode = (value: 'table' | 'cards') => {
  listViewMode.value = value
}

const resetQuickFilters = () => {
  selectedReviewStatus.value = 'all'
  analysisFilter.value = 'all'
  modelFilter.value = ''
  page.value = 1
}

useDocumentsRouteState({
  page,
  pageSize,
  ordering,
  selectedTag,
  selectedCorrespondent,
  selectedReviewStatus,
  dateFrom,
  dateTo,
  analysisFilter,
  modelFilter,
  viewMode: listViewMode,
})

onMounted(async () => {
  if (!hasExplicitViewQuery.value && window.matchMedia('(max-width: 767px)').matches) {
    listViewMode.value = 'cards'
  }
  await load()
})

</script>
