<template>
  <section>
    <DocumentsHeaderSection
      :visible-count="visibleDocuments.length"
      :total-count="totalCount"
      :search-label="searchQuery.trim()"
      :stats="stats"
      :queued-count="queueStatus.enabled ? (queueStatus.length ?? 0) : 0"
      :is-processing="isProcessing"
      :sync-status="syncStatus"
      :embed-status="embedStatus"
      :has-queued-work="hasQueuedWork"
      :show-cancel="showCancel"
      :progress-percent="progressPercent"
      :eta-text="etaText"
      :embed-label="embedLabel"
      :processing-processed="processingProcessed"
      :processing-total="processingTotal"
      :processing-percent="processingPercent"
      :processing-eta-text="processingEtaText"
      :last-run-text="lastRunText"
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
      :issue-date-is-import-date="issueDateIsImportDate"
      :preset-counts="presetCounts"
      @reload="load"
      @apply-preset="applyTriagePreset"
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
      :issue-date-is-import-date="issueDateIsImportDate"
      @clear-filter="clearFilter"
      @clear-all="clearAllFilters"
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
      @retry="load"
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
      :doc-href="docHref"
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
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useToastStore } from '../stores/toastStore'
import { useDocumentsCatalog } from '../composables/useDocumentsCatalog'
import { useReviewSummary } from '../composables/useReviewSummary'
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
import DocumentsHeaderSection from '../components/DocumentsHeaderSection.vue'
import DocumentsQuickControls from '../components/DocumentsQuickControls.vue'
import DocumentsTable from '../components/DocumentsTable.vue'
import { createReviewQueueState, saveReviewQueueState } from '../utils/reviewQueue'
import { clearLastPreset, readLastPreset, writeLastPreset } from '../utils/documentsPresetStorage'

const router = useRouter()
const route = useRoute()
const toastStore = useToastStore()
const listViewMode = ref<'table' | 'cards'>('table')
const includeSummaryPreview = computed(() => listViewMode.value === 'cards')
const {
  documents,
  listRequest,
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
  searchQuery,
  issueDateIsImportDate,
  documentsLoading,
  documentsError,
  refetchDocuments,
} = useDocumentsCatalog({ includeSummaryPreview })
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
const runningOnly = ref(false)
const { visibleDocuments: filteredDocuments } = useVisibleDocuments(
  documents,
  analysisFilter,
  modelFilter,
)
const { runningByDocId } = useRunningTaskProgress()

// Library-wide counters on the presets (what is left to work through).
const { summary: reviewSummary } = useReviewSummary()
const presetCounts = computed(() => {
  const summary = reviewSummary.value
  if (!summary) return undefined
  return {
    unreviewed: summary.unreviewed,
    needs_review: summary.needs_review,
    no_correspondent: summary.no_correspondent,
    import_date: summary.issue_date_is_import_date,
  }
})
const visibleDocuments = computed(() => {
  if (!runningOnly.value) return filteredDocuments.value
  return filteredDocuments.value.filter((doc) =>
    typeof doc.id === 'number' ? Boolean(runningByDocId.value[doc.id]) : false,
  )
})
// Keep the ordered ids of the visible list so the detail view can offer previous/next
// (also for links opened in a new tab).
const emptyStateMode = computed<'filtered' | 'running_only' | 'empty' | 'error'>(() => {
  if (runningOnly.value) return 'running_only'
  if (documentsError.value && documents.value.length === 0) return 'error'
  if (documents.value.length === 0) return 'empty'
  return 'filtered'
})

const totalPages = computed(() => Math.max(1, Math.ceil(totalCount.value / pageSize.value)))

// Remember the visible list and how it was loaded so the detail view can offer
// previous/next, continue on further pages and (for stable lists) go back a page.
watch(
  [
    () => visibleDocuments.value.map((doc) => doc.id),
    listRequest,
    page,
    totalPages,
    analysisFilter,
    modelFilter,
    runningOnly,
  ],
  () => {
    const status = selectedReviewStatus.value
    saveReviewQueueState(
      createReviewQueueState(
        visibleDocuments.value.map((doc) => doc.id),
        {
          firstPage: page.value,
          lastPage: page.value,
          totalPages: totalPages.value,
          shrinking: status === 'unreviewed' || status === 'needs_review',
          // "Running only" depends on live task state, so paging is disabled for it.
          request: runningOnly.value ? null : listRequest.value,
          clientFilter: { analysis: analysisFilter.value, model: modelFilter.value },
          suggestionIds: visibleDocuments.value
            .filter((doc) => doc.has_suggestions && typeof doc.id === 'number')
            .map((doc) => doc.id as number),
        },
      ),
    )
  },
  { immediate: true },
)
const {
  isProcessing,
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

const isValidDocId = (id: number) => Number.isFinite(id) && id > 0

const docHref = (id: number, tab?: 'operations' | 'suggestions') =>
  router.resolve({
    path: `/documents/${id}`,
    query: {
      return_to: encodeURIComponent(route.fullPath),
      ...(tab ? { tab } : {}),
    },
  }).href

const open = (id: number) => {
  if (!isValidDocId(id)) {
    toastStore.push('Invalid document ID.', 'warning', 'Documents')
    return
  }
  router.push({
    path: `/documents/${id}`,
    query: { return_to: encodeURIComponent(route.fullPath) },
  })
}

const openOperations = (id: number) => {
  if (!isValidDocId(id)) {
    toastStore.push('Invalid document ID.', 'warning', 'Documents')
    return
  }
  router.push({
    path: `/documents/${id}`,
    query: {
      return_to: encodeURIComponent(route.fullPath),
      tab: 'operations',
    },
  })
}

const openSuggestions = (id: number) => {
  if (!isValidDocId(id)) {
    toastStore.push('Invalid document ID.', 'warning', 'Documents')
    return
  }
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
  issueDateIsImportDate.value = false
  page.value = 1
  clearLastPreset()
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
    | 'running_only'
    | 'import_date',
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
  if (key === 'import_date') issueDateIsImportDate.value = false
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
  issueDateIsImportDate.value = false
  page.value = 1
  clearLastPreset()
}

const applyTriagePreset = (
  key: 'unreviewed' | 'needs_review' | 'not_analyzed' | 'inbox' | 'no_correspondent' | 'import_date',
) => {
  // Filter presets keep the other filters (e.g. review status) and toggle on/off.
  if (key === 'no_correspondent') {
    selectedCorrespondent.value = selectedCorrespondent.value === '-1' ? '' : '-1'
    // Toggling the filter off forgets it; toggling on remembers it.
    if (selectedCorrespondent.value === '-1') writeLastPreset('no_correspondent')
    else clearLastPreset()
    page.value = 1
    return
  }
  if (key === 'import_date') {
    issueDateIsImportDate.value = !issueDateIsImportDate.value
    if (issueDateIsImportDate.value) writeLastPreset('import_date')
    else clearLastPreset()
    page.value = 1
    return
  }
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
  writeLastPreset(key)
}

// The URL carries an explicit list filter when any of these query keys is set.
// A "clean" URL (none of them) is when we restore the remembered preset.
const LIST_FILTER_QUERY_KEYS = [
  'review_status',
  'analysis_filter',
  'correspondent',
  'import_date',
  'q',
  'tag',
  'model',
  'running_only',
  'date_from',
  'date_to',
] as const

const hasExplicitListFilter = (): boolean =>
  LIST_FILTER_QUERY_KEYS.some((key) => {
    const value = route.query[key]
    const single = Array.isArray(value) ? value[0] : value
    return Boolean(single && String(single).trim() !== '')
  })

const restoreRememberedPreset = () => {
  const key = readLastPreset()
  if (!key || hasExplicitListFilter()) return
  applyTriagePreset(key)
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
  issueDateIsImportDate,
  viewMode: listViewMode,
})

onMounted(() => {
  if (!hasExplicitViewQuery.value && window.matchMedia('(max-width: 767px)').matches) {
    listViewMode.value = 'cards'
  }
  // Restore the last applied preset only when the URL does not already carry an
  // explicit list filter (so a shared/filtered link wins over the remembered one).
  // Runs after useDocumentsRouteState has applied the URL query to the refs.
  restoreRememberedPreset()
})

</script>
