<template>
  <section>
    <div class="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
      <div>
        <h2 class="text-2xl font-semibold tracking-tight">Documents</h2>
        <p class="text-sm text-slate-500">
          Manage ingestion, embedding, and review analysis status.
        </p>
        <p class="mt-1 text-xs text-slate-500 dark:text-slate-400">
          Showing {{ visibleDocuments.length }} of {{ totalCount }} synced documents
          <template v-if="searchQuery.trim()">
            for "{{ searchQuery.trim() }}"
          </template>
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
      v-model:search-query="searchQuery"
      v-model:page-size="pageSize"
      :is-loading="documentsLoading"
      @reload="load"
    />

    <DocumentsActiveFiltersStrip
      :tags="tags"
      :correspondents="correspondents"
      :selected-correspondent="selectedCorrespondent"
      :selected-tag="selectedTag"
      :date-from="dateFrom"
      :date-to="dateTo"
      :analysis-filter="analysisFilter"
      :selected-review-status="selectedReviewStatus"
      :model-filter="modelFilter"
      :search-query="searchQuery"
      :running-only="runningOnly"
      @clear-filter="clearFilter"
      @clear-all="clearAllFilters"
    />

    <DocumentsPresetBar
      :analysis-filter="analysisFilter"
      :review-status="selectedReviewStatus"
      :search-query="searchQuery"
      @apply-preset="applyTriagePreset"
    />

    <DocumentsQuickControls
      :view-mode="listViewMode"
      :running-only="runningOnly"
      @update:viewMode="setListViewMode"
      @update:runningOnly="setRunningOnly"
      @reset-quick-filters="resetQuickFilters"
      @clear-all-filters="clearAllFilters"
      @open-writeback="openWritebackQueue"
      @open-processing="openPreview"
    />

    <DocumentsEmptyState
      v-if="visibleDocuments.length === 0"
      :mode="emptyStateMode"
      @clear-filters="clearAllFilters"
      @open-processing="openPreview"
    />

    <DocumentsTable
      v-else
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
      @open-doc-suggestions="openSuggestions"
      @prev-page="onPrevPage"
      @next-page="onNextPage"
      @jump-page="onJumpPage"
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
import DocumentsActiveFiltersStrip from '../components/DocumentsActiveFiltersStrip.vue'
import DocumentsEmptyState from '../components/DocumentsEmptyState.vue'
import DocumentsPresetBar from '../components/DocumentsPresetBar.vue'
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
  documentsLoading,
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
const searchQuery = ref('')
const runningOnly = ref(false)
const listViewMode = ref<'table' | 'cards'>('table')
const { visibleDocuments: filteredDocuments } = useVisibleDocuments(
  documents,
  analysisFilter,
  modelFilter,
  searchQuery,
)
const { runningByDocId } = useRunningTaskProgress()
const visibleDocuments = computed(() => {
  if (!runningOnly.value) return filteredDocuments.value
  return filteredDocuments.value.filter((doc) =>
    typeof doc.id === 'number' ? Boolean(runningByDocId.value[doc.id]) : false,
  )
})
const emptyStateMode = computed<'filtered' | 'running_only' | 'empty'>(() => {
  if (runningOnly.value) return 'running_only'
  if (documents.value.length === 0) return 'empty'
  return 'filtered'
})

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

const onJumpPage = async (targetPage: number) => {
  if (targetPage < 1 || targetPage > totalPages.value) return
  page.value = targetPage
  await load()
}

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

const openSuggestions = (id: number) => {
  router.push({
    path: `/documents/${id}`,
    query: {
      return_to: encodeURIComponent(route.fullPath),
      tab: 'suggestions',
    },
  })
}

const hasExplicitViewQuery = computed(() => {
  const value = route.query.view
  const normalized = Array.isArray(value) ? value[0] : value
  return normalized === 'cards' || normalized === 'table'
})

const setListViewMode = (value: 'table' | 'cards') => {
  listViewMode.value = value
}

const setRunningOnly = (value: boolean) => {
  runningOnly.value = value
  page.value = 1
}

const resetQuickFilters = () => {
  selectedReviewStatus.value = 'all'
  analysisFilter.value = 'all'
  modelFilter.value = ''
  searchQuery.value = ''
  runningOnly.value = false
  page.value = 1
}

const clearFilter = (
  key:
    | 'correspondent'
    | 'tag'
    | 'date_from'
    | 'date_to'
    | 'analysis'
    | 'review'
    | 'model'
    | 'search'
    | 'running_only',
) => {
  if (key === 'correspondent') selectedCorrespondent.value = ''
  if (key === 'tag') selectedTag.value = ''
  if (key === 'date_from') dateFrom.value = ''
  if (key === 'date_to') dateTo.value = ''
  if (key === 'analysis') analysisFilter.value = 'all'
  if (key === 'review') selectedReviewStatus.value = 'all'
  if (key === 'model') modelFilter.value = ''
  if (key === 'search') searchQuery.value = ''
  if (key === 'running_only') runningOnly.value = false
  page.value = 1
}

const clearAllFilters = () => {
  selectedCorrespondent.value = ''
  selectedTag.value = ''
  dateFrom.value = ''
  dateTo.value = ''
  selectedReviewStatus.value = 'all'
  analysisFilter.value = 'all'
  modelFilter.value = ''
  searchQuery.value = ''
  runningOnly.value = false
  page.value = 1
}

const applyTriagePreset = (key: 'unreviewed' | 'needs_review' | 'not_analyzed' | 'inbox') => {
  if (key === 'unreviewed') {
    selectedReviewStatus.value = 'unreviewed'
    analysisFilter.value = 'all'
  }
  if (key === 'needs_review') {
    selectedReviewStatus.value = 'needs_review'
    analysisFilter.value = 'all'
  }
  if (key === 'not_analyzed') {
    selectedReviewStatus.value = 'all'
    analysisFilter.value = 'not_analyzed'
  }
  if (key === 'inbox') {
    selectedReviewStatus.value = 'unreviewed'
    analysisFilter.value = 'not_analyzed'
  }
  searchQuery.value = ''
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
  searchQuery,
  runningOnly,
  viewMode: listViewMode,
})

onMounted(async () => {
  if (!hasExplicitViewQuery.value && window.matchMedia('(max-width: 767px)').matches) {
    listViewMode.value = 'cards'
  }
  await load()
})

</script>
