<template>
  <section>
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-2xl font-semibold tracking-tight">Documents</h2>
        <p class="text-sm text-slate-500">
          Manage ingestion, embedding, and review analysis status.
        </p>
      </div>
      <div class="flex items-center gap-3">
        <div
          class="grid grid-cols-4 gap-x-3 gap-y-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600 shadow-sm dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
        >
          <div class="text-slate-500">Synced</div>
          <div class="font-semibold text-slate-900 dark:text-slate-100">{{ stats.total }}</div>
          <div class="text-slate-500">Queued</div>
          <div class="font-semibold text-indigo-600">
            {{ queueStatus.enabled ? (queueStatus.length ?? 0) : 0 }}
          </div>

          <div class="text-slate-500">Embeddings</div>
          <div class="font-semibold text-emerald-600">{{ stats.embeddings }}</div>
          <div class="text-slate-500">Vision OCR</div>
          <div class="font-semibold text-emerald-600">{{ stats.vision }}</div>

          <div class="text-slate-500">Suggestions</div>
          <div class="font-semibold text-emerald-600">{{ stats.suggestions }}</div>
          <div class="text-slate-500">Fully processed</div>
          <div class="font-semibold text-emerald-700 dark:text-emerald-400">
            {{ stats.fully_processed }}
          </div>

          <div class="text-slate-500">Pending</div>
          <div class="font-semibold text-amber-600">{{ stats.unprocessed }}</div>
          <div class="text-slate-500">Processed*</div>
          <div class="font-semibold text-emerald-600">{{ stats.processed }}</div>
        </div>
        <div
          v-if="isProcessing"
          class="flex items-center gap-3 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600 shadow-sm dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
        >
          <Loader2 class="h-4 w-4 animate-spin text-indigo-500" />
          <div class="space-y-0.5">
            <div v-if="syncStatus.status === 'running'">
              Sync {{ syncStatus.processed }} / {{ syncStatus.total }} ({{ progressPercent }}%) -
              ETA {{ etaText }}
            </div>
            <div v-if="embedStatus.status === 'running' || hasQueuedWork">
              {{ embedLabel }} {{ processingProcessed }} / {{ processingTotal }} ({{
                processingPercent
              }}%) - ETA {{ processingEtaText }}
            </div>
            <div
              v-if="hasQueuedWork && lastRunText !== '--'"
              class="text-xs text-slate-500 dark:text-slate-400"
            >
              Last run: {{ lastRunText }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <section
      class="mt-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900"
    >
      <div class="flex w-full flex-wrap items-center justify-end gap-3">
        <button
          class="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
          :disabled="continueProcessingRunning || isProcessing"
          @click="openPreview"
          title="Sync new documents and process missing intelligence items"
        >
          <RefreshCw class="h-4 w-4" />
          {{ continueProcessingRunning ? 'Working...' : 'Continue processing' }}
        </button>
        <button
          v-if="showCancel"
          class="inline-flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm font-semibold text-rose-700 shadow-sm hover:border-rose-300 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-200"
          @click="cancelProcessing"
          title="Cancel processing and clear queued jobs"
        >
          <XCircle class="h-4 w-4" />
          Cancel processing
        </button>
      </div>
    </section>

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
    @update:batch-index="batchIndex = $event"
    @close="closePreview"
    @start="startFromPreview"
  />
</template>

<script setup lang="ts">
import { computed, onMounted, watch, ref } from 'vue'
import {
  Loader2,
  RefreshCw,
  XCircle,
} from 'lucide-vue-next'
import { useRouter } from 'vue-router'
import { useToastStore } from '../stores/toastStore'
import { useContinueProcessing } from '../composables/useContinueProcessing'
import { useContinueProcessOptions } from '../composables/useContinueProcessOptions'
import { useDocumentsCatalog } from '../composables/useDocumentsCatalog'
import { useDocumentsProcessingActions } from '../composables/useDocumentsProcessingActions'
import { useProcessingOverview } from '../composables/useProcessingOverview'
import { useProcessingMetrics } from '../composables/useProcessingMetrics'
import { usePaperlessBaseUrl } from '../composables/usePaperlessBaseUrl'
import { useVisibleDocuments } from '../composables/useVisibleDocuments'
import ContinueProcessingModal from '../components/ContinueProcessingModal.vue'
import DocumentsFiltersPanel from '../components/DocumentsFiltersPanel.vue'
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
const sortDir = (field: string) => {
  const current = ordering.value.replace('-', '')
  if (current !== field) return null
  return ordering.value.startsWith('-') ? 'desc' : 'asc'
}

const toggleSort = (field: string) => {
  const dir = sortDir(field)
  if (!dir || dir === 'desc') {
    ordering.value = field
  } else {
    ordering.value = `-${field}`
  }
  page.value = 1
}

const load = async () => {
  try {
    await refetchDocuments()
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to load documents'
    toastStore.push(message, 'danger', 'Error')
  }
}
const { openPreview, closePreview, startFromPreview, cancelProcessing } = useDocumentsProcessingActions(
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

const open = (id: number) => {
  router.push(`/documents/${id}`)
}

const onPrevPage = async () => {
  if (page.value <= 1) return
  page.value -= 1
  await load()
}

const onNextPage = async () => {
  if (page.value >= totalPages.value) return
  page.value += 1
  await load()
}

onMounted(async () => {
  await load()
})

watch(
  () => ({ ...processOptions }),
  async () => {
    if (!showPreviewModal.value) return
    try {
      await refreshProcessPreview(processParams())
    } catch {
      // Keep current preview shown when transient refresh fails.
    }
  },
  { deep: true },
)

watch(batchIndex, async () => {
  if (!showPreviewModal.value) return
  try {
    await refreshProcessPreview(processParams())
  } catch {
    // Keep current preview shown when transient refresh fails.
  }
})

</script>
