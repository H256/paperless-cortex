<template>
  <section>
    <div class="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h2 class="text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">
          {{ document?.title || `Document ${id}` }}
        </h2>
        <p class="text-sm text-slate-500 dark:text-slate-400">{{ headerMetaLine }}</p>
        <p
          v-if="activeRunLabel"
          class="mt-1 inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-indigo-50 px-2.5 py-1 text-xs font-semibold text-indigo-700 dark:border-indigo-900/50 dark:bg-indigo-950/30 dark:text-indigo-200"
        >
          Processing now: {{ activeRunLabel }}
        </p>
      </div>
      <div class="flex w-full flex-wrap items-center gap-2 md:w-auto md:justify-end">
        <button
          class="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 shadow-sm hover:border-slate-300 sm:text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
          @click="navigateBackToDocuments"
        >
          <ArrowLeft class="h-4 w-4" />
          Back
        </button>
        <IconButton
          v-if="paperlessUrl"
          :href="paperlessUrl"
          title="Open document in Paperless"
          aria-label="Open document in Paperless"
        >
          <ExternalLink class="h-5 w-5" />
        </IconButton>
        <IconButton
          v-else
          disabled
          title="Set VITE_PAPERLESS_BASE_URL to enable link"
          aria-label="Paperless link unavailable"
        >
          <ExternalLink class="h-5 w-5" />
        </IconButton>
        <button
          class="inline-flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-700 shadow-sm hover:border-emerald-300 sm:text-sm dark:border-emerald-900/50 dark:bg-emerald-950/30 dark:text-emerald-200"
          :disabled="reviewMarking || !canMarkReviewed"
          :class="reviewMarking || !canMarkReviewed ? 'cursor-not-allowed opacity-70' : ''"
          title="Marks this document as reviewed without applying suggestions."
          @click="markReviewedAction"
        >
          <CheckCircle class="h-4 w-4" :class="reviewMarking ? 'animate-pulse' : ''" />
          {{ reviewMarking ? 'Marking...' : 'Mark reviewed' }}
        </button>
        <button
          class="inline-flex items-center gap-2 rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-2 text-xs font-semibold text-indigo-700 shadow-sm hover:border-indigo-300 sm:text-sm dark:border-indigo-900/50 dark:bg-indigo-950/30 dark:text-indigo-200"
          :disabled="writebackRunning || !canWriteback"
          :class="writebackRunning || !canWriteback ? 'cursor-not-allowed opacity-70' : ''"
          :title="writebackButtonTitle"
          @click="openWritebackConfirm"
        >
          <ClipboardCheck class="h-4 w-4" :class="writebackRunning ? 'animate-pulse' : ''" />
          {{ writebackButtonLabel }}
        </button>
        <button
          class="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-3 py-2 text-xs font-semibold text-white shadow-sm hover:bg-slate-800 sm:text-sm"
          :disabled="reloadingAll"
          :class="reloadingAll ? 'cursor-not-allowed opacity-70' : ''"
          @click="reloadAll"
        >
          <RefreshCw class="h-4 w-4" :class="reloadingAll ? 'animate-spin' : ''" />
          {{ reloadingAll ? 'Reloading...' : 'Reload' }}
        </button>
      </div>
    </div>

    <div v-if="loading" class="mt-6 text-sm text-slate-500">Loading...</div>
    <div v-else class="mt-6 space-y-4">
      <div class="rounded-xl border border-slate-200 bg-white p-2 text-xs font-semibold text-slate-600 shadow-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200">
        <div class="overflow-x-auto">
          <div class="flex min-w-max items-center gap-2">
            <button
              v-for="tab in tabs"
              :key="tab.key"
              class="rounded-lg px-3 py-1.5"
              :class="
                activeTab === tab.key
                  ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700'
              "
              @click="activeTab = tab.key"
            >
              {{ tab.label }}
            </button>
          </div>
        </div>
      </div>

      <DocumentMetadataSection v-if="activeTab === 'meta'" :rows="rows" />

      <DocumentTextQualitySection
        v-if="activeTab === 'text'"
        :content="document?.content || ''"
        :content-quality="contentQuality"
        :content-quality-error="contentQualityError"
        :ocr-scores="ocrScores"
        :ocr-scores-loading="ocrScoresLoading"
        :ocr-scores-error="ocrScoresError"
      />

      <DocumentSuggestionsSection
        v-if="activeTab === 'suggestions'"
        :suggestions="suggestions"
        :suggestions-error="suggestionsError"
        :suggestions-loading="suggestionsLoading"
        :suggestion-variants="suggestionVariants"
        :suggestion-variant-loading="suggestionVariantLoading"
        :suggestion-variant-error="suggestionVariantError"
        :current-values="currentValues"
        @refresh="refreshSuggestionsAction"
        @suggest-field="suggestFieldAction"
        @apply-variant="applyVariantOnly"
        @apply-variant-to-document="applyVariantToDocument"
        @apply-to-document="applyToDocument"
      />

      <DocumentPagesSection
        v-if="activeTab === 'pages'"
        :page-texts="pageTexts"
        :vision-progress="pageTextsVisionProgress"
        :page-texts-error="pageTextsError"
        :aggregated-text="aggregatedText"
        :pdf-page="pdfPage"
        @jump-to-page="onPdfPageChange"
      />

      <DocumentOperationsSection
        v-if="activeTab === 'operations'"
        :continue-pipeline-loading="continuePipelineLoading"
        :continue-queued-waiting="continueQueuedWaiting"
        :has-active-task-runs="hasActiveTaskRuns"
        :doc-ops-loading="docOpsLoading"
        :pipeline-status-loading="pipelineStatusLoading"
        :pipeline-status-error="pipelineStatusError"
        :processing-done-count="processingDoneCount"
        :processing-required-count="processingRequiredCount"
        :pipeline-preferred-source="pipelinePreferredSource"
        :is-large-document-mode="isLargeDocumentMode"
        :large-document-hint="largeDocumentHint"
        :processing-status-items="processingStatusItems"
        :pipeline-fanout-loading="pipelineFanoutLoading"
        :pipeline-fanout-error="pipelineFanoutError"
        :pipeline-fanout-items="pipelineFanoutItems"
        :timeline-status-filter="timelineStatusFilter"
        :timeline-query-filter="timelineQueryFilter"
        :task-runs-loading="taskRunsLoading"
        :task-runs-error="taskRunsError || ''"
        :task-runs="taskRuns as never"
        :doc-cleanup-clear-first="docCleanupClearFirst"
        :doc-ops-message="docOpsMessage"
        :operation-actions="operationActions as never"
        :to-title="toTitle"
        :processing-badge-class="processingBadgeClass"
        :processing-state-label="processingStateLabel"
        :fanout-status-class="fanoutStatusClass"
        :to-relative-time="toRelativeTime"
        :to-date-time="toDateTime"
        :checkpoint-label="checkpointLabelFromUnknown"
        :embedding-telemetry-label="embeddingTelemetryLabelFromUnknown"
        :compact-error-message="compactErrorMessage"
        @continue-pipeline="runContinuePipeline"
        @open-queue="router.push('/queue')"
        @open-logs="router.push('/logs')"
        @reload-fanout="reloadPipelineFanout"
        @update:timeline-status-filter="timelineStatusFilter = $event"
        @update:timeline-query-filter="timelineQueryFilter = $event"
        @refresh-task-runs="refreshTaskRuns"
        @retry-task-run="retryTaskRun($event as TimelineTaskRun)"
        @copy-run-error="copyRunError"
        @update:doc-cleanup-clear-first="docCleanupClearFirst = $event"
        @run-doc-cleanup="runDocCleanup"
        @enqueue-doc-task="enqueueDocTask($event as OperationAction)"
        @open-reset-confirm="openResetConfirm"
      />

      <PdfViewer
        class="mt-6"
        :pdf-url="pdfUrl"
        v-model:page="pdfPage"
        :highlights="pdfHighlights"
        @update:page="onPdfPageChange"
      />

      <ConfirmDialog
        :open="resetConfirmOpen"
        title="Reset document and reprocess?"
        message="This deletes local intelligence data for this document, resyncs metadata/content from Paperless, and re-enqueues processing."
        confirm-label="Reset + Reprocess"
        @confirm="confirmResetAndReprocessDoc"
        @cancel="resetConfirmOpen = false"
      />
      <ConfirmDialog
        :open="writebackConfirmOpen"
        title="Write changes to Paperless?"
        message="This updates metadata and AI summary note in Paperless immediately for this document."
        confirm-label="Write now"
        cancel-label="Cancel"
        @confirm="confirmWritebackNow"
        @cancel="closeWritebackConfirm"
      />
      <WritebackConflictModal
        :open="writebackConflictOpen"
        :running="writebackRunning"
        :conflicts="writebackConflicts"
        :resolutions="writebackResolutions"
        @cancel="cancelWritebackConflict"
        @apply="applyWritebackConflictResolutions"
        @set-resolution="setConflictResolution"
      />
      <ConfirmDialog
        :open="writebackErrorOpen"
        title="Writeback failed"
        :message="writebackErrorMessage || 'Unknown error'"
        confirm-label="Close"
        cancel-label="Close"
        @confirm="closeWritebackError"
        @cancel="closeWritebackError"
      />

    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ArrowLeft, CheckCircle, ClipboardCheck, ExternalLink, RefreshCw } from 'lucide-vue-next'
import { useRoute, useRouter } from 'vue-router'
import IconButton from '../components/IconButton.vue'
import DocumentMetadataSection from '../components/DocumentMetadataSection.vue'
import DocumentTextQualitySection from '../components/DocumentTextQualitySection.vue'
import DocumentSuggestionsSection from '../components/DocumentSuggestionsSection.vue'
import DocumentPagesSection from '../components/DocumentPagesSection.vue'
import DocumentOperationsSection from '../components/DocumentOperationsSection.vue'
import WritebackConflictModal from '../components/WritebackConflictModal.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import PdfViewer from '../components/PdfViewer.vue'
import { useToastStore } from '../stores/toastStore'
import { useDocumentPipeline } from '../composables/useDocumentPipeline'
import { useDocumentOperations } from '../composables/useDocumentOperations'
import { useDocumentDetailData } from '../composables/useDocumentDetailData'
import { useAutoRefresh } from '../composables/useAutoRefresh'
import { useDocumentWriteback } from '../composables/useDocumentWriteback'
import { useDocumentReview } from '../composables/useDocumentReview'
import { usePaperlessBaseUrl } from '../composables/usePaperlessBaseUrl'
import { useDocumentTaskRuns } from '../composables/useDocumentTaskRuns'
import { useDocumentSuggestionsApply } from '../composables/useDocumentSuggestionsApply'
import {
  detailTabs,
  useDocumentDetailRouteState,
} from '../composables/useDocumentDetailRouteState'
import {
  useDocumentDetailOperations,
  type OperationAction,
  type TimelineTaskRun,
} from '../composables/useDocumentDetailOperations'
import {
  fanoutStatusClass,
  processingBadgeClass,
  processingStateLabel,
  useDocumentProcessingState,
} from '../composables/useDocumentProcessingState'
import { formatDateTime, formatRelativeTime } from '../utils/dateTime'
import { formatCheckpointLabel } from '../utils/taskRunCheckpoint'
import {
  compactErrorMessage,
  embeddingTelemetryLabel,
  errorMessage,
  formatDocDate,
  toDateTime,
  toTitle,
} from '../utils/documentDetail'

const route = useRoute()
const router = useRouter()
const id = Number(route.params.id)
const {
  activeTab,
  pdfPage,
  pdfHighlights,
  returnToDocumentsPath,
  syncPdfFromQuery,
  syncTabFromQuery,
  syncTabToQuery,
  onPdfPageChange,
} = useDocumentDetailRouteState(route, router)

const toastStore = useToastStore()
const { paperlessBaseUrl } = usePaperlessBaseUrl()
const {
  document,
  loading,
  tags,
  correspondents,
  docTypes,
  pageTexts,
  pageTextsVisionProgress,
  pageTextsError,
  contentQuality,
  contentQualityError,
  ocrScores,
  ocrScoresLoading,
  ocrScoresError,
  suggestions,
  suggestionsLoading,
  suggestionsError,
  suggestionVariants,
  suggestionVariantLoading,
  suggestionVariantError,
  loadDocument,
  loadMeta,
  loadPageTexts,
  loadContentQuality,
  loadOcrScores,
  loadSuggestions,
  refreshSuggestions: refreshSuggestionsForSource,
  suggestField,
  applyVariant,
  applyToDocument: applySuggestionToDocument,
} = useDocumentDetailData()
const {
  pipelineStatus,
  pipelineStatusLoading,
  pipelineStatusError,
  pipelineFanout,
  pipelineFanoutLoading,
  pipelineFanoutError,
  refreshPipelineStatus,
  refreshPipelineFanout,
  continuePipeline: continuePipelineRequest,
  continuePipelineLoading,
} = useDocumentPipeline(computed(() => id))
const {
  loading: docOpsLoading,
  enqueueTask: enqueueDocumentTaskNow,
  cleanup: cleanupDocumentTexts,
  resetAndReprocess: resetAndReprocessNow,
} = useDocumentOperations(computed(() => id))
const timelineStatusFilter = ref('')
const timelineQueryFilter = ref('')
const {
  taskRuns,
  taskRunsLoading,
  taskRunsError,
  refreshTaskRuns,
} = useDocumentTaskRuns(() => id, {
  status: timelineStatusFilter,
  query: timelineQueryFilter,
})

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || '/api'
const pdfUrl = computed(() => `${apiBaseUrl}/documents/${id}/pdf`)
const tabs = detailTabs
const reloadingAll = ref(false)
const paperlessUrl = computed(() =>
  paperlessBaseUrl.value && document.value
    ? `${paperlessBaseUrl.value.replace(/\/$/, '')}/documents/${document.value.id}`
    : '',
)

const aggregatedText = computed(() => {
  if (!pageTexts.value.length) return document.value?.content || ''
  return pageTexts.value.map((page) => page.text).join('\n\n')
})

const suggestFieldAction = async (source: 'paperless_ocr' | 'vision_ocr', field: string) => {
  await suggestField(id, source, field)
}

const currentNotePreview = computed(() =>
  (document.value?.notes || [])
    .map((note) => note.note)
    .filter(Boolean)
    .join(' ')
    .trim(),
)

const currentTagNames = computed(() =>
  (document.value?.tags || [])
    .map((tagId) => tags.value.find((tag) => tag.id === tagId)?.name ?? tagId)
    .join(', '),
)

const currentCorrespondentName = computed(() => {
  if (!document.value) return ''
  const value =
    document.value.correspondent_name ??
    correspondents.value.find((c) => c.id === document.value?.correspondent)?.name ??
    document.value.correspondent ??
    ''
  return String(value)
})

const currentValues = computed(() => ({
  title: document.value?.title || '',
  date: formatDocDate(document.value?.document_date || document.value?.created) || '',
  correspondent: currentCorrespondentName.value || '',
  tags: currentTagNames.value || '',
  note: currentNotePreview.value || '',
}))
const canMarkReviewed = computed(
  () =>
    Boolean(document.value) &&
    !document.value?.local_overrides &&
    String(document.value?.review_status || '').toLowerCase() !== 'reviewed',
)
const { reviewMarking, markReviewed } = useDocumentReview(computed(() => id))

const rows = computed(() => {
  if (!document.value) return []
  const notes = (document.value.notes || []).map((n) => n.note).join(' ')
  const tagNames = (document.value.tags || [])
    .map((tagId) => tags.value.find((t) => t.id === tagId)?.name ?? tagId)
    .join(', ')
  const pendingTagNames = (document.value.pending_tag_names || []).join(', ')
  const correspondentName =
    document.value.correspondent_name ??
    correspondents.value.find((c) => c.id === document.value?.correspondent)?.name ??
    document.value.correspondent
  const docTypeName =
    document.value.document_type_name ??
    docTypes.value.find((d) => d.id === document.value?.document_type)?.name ??
    document.value.document_type
  const createdLabel = formatDateTime(document.value.created) || '-'
  const modifiedLabel = formatDateTime(document.value.modified) || '-'
  return [
    { label: 'Title', value: document.value.title },
    { label: 'Issue date', value: formatDocDate(document.value.document_date || document.value.created) },
    { label: 'Correspondent', value: correspondentName },
    { label: 'Document type', value: docTypeName },
    { label: 'Tags', value: tagNames, pendingValue: pendingTagNames || null },
    {
      label: 'Original filename',
      value: document.value.original_file_name,
      className: 'md:col-span-2',
    },
    {
      label: 'Timestamps',
      value: `Created: ${createdLabel}\nModified: ${modifiedLabel}`,
    },
    { label: 'Notes', value: notes },
  ]
})

const headerMetaLine = computed(() => {
  const syncAt = formatDateTime(document.value?.modified)
  const reviewStatus = toTitle(document.value?.review_status || '')
  const reviewedAt = formatDateTime(document.value?.reviewed_at)
  const reviewPart = reviewedAt ? `${reviewStatus} (${reviewedAt})` : reviewStatus
  return `Document ID: ${id}, Synced at: ${syncAt || '-'}, ${reviewPart || 'Unknown'}`
})

const navigateBackToDocuments = async () => {
  await router.push(returnToDocumentsPath.value)
}

const markReviewedAction = async () => {
  if (!canMarkReviewed.value || reviewMarking.value) return
  try {
    const result = await markReviewed()
    if (result.status === 'missing') {
      toastStore.push('Document not found locally.', 'warning', 'Review', 2200)
      return
    }
    await load()
    toastStore.push('Document marked as reviewed.', 'success', 'Review', 1800)
  } catch (err: unknown) {
    toastStore.push(errorMessage(err, 'Failed to mark document reviewed'), 'danger', 'Review', 2800)
  }
}

const toRelativeTime = (value?: string | null) => {
  return formatRelativeTime(value)
}

function checkpointLabel(checkpoint?: Record<string, unknown> | null) {
  return formatCheckpointLabel(checkpoint, '-')
}

const checkpointLabelFromUnknown = (value?: unknown) =>
  checkpointLabel(value && typeof value === 'object' ? (value as Record<string, unknown>) : null)

const embeddingTelemetryLabelFromUnknown = (value?: unknown) =>
  embeddingTelemetryLabel(
    value && typeof value === 'object' ? (value as Record<string, unknown>) : null,
  )

const copyRunError = async (message?: string | null) => {
  const text = String(message || '').trim()
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    toastStore.push('Error copied to clipboard.', 'success', 'Processing timeline', 1800)
  } catch {
    toastStore.push('Failed to copy error message.', 'danger', 'Processing timeline', 2400)
  }
}

const load = async () => {
  await loadDocument(id)
}

const loadMetaForDoc = async () => {
  await loadMeta()
}

const loadPageTextsForDoc = async (priority = false) => {
  await loadPageTexts(id, priority)
}

const loadContentQualityForDoc = async (priority = false) => {
  await loadContentQuality(id, priority)
  await loadOcrScores(id, priority)
}

const loadSuggestionsForDoc = async () => {
  await loadSuggestions(id)
}

const {
  applyVariantOnly,
  applyVariantToDocument,
  applyToDocument,
} = useDocumentSuggestionsApply({
  docId: id,
  suggestions,
  pageTexts,
  contentQuality,
  suggestionsError,
  applyVariant,
  applySuggestionToDocument,
  loadDocument: load,
  loadSuggestionsForDoc,
  loadPageTextsForDoc,
  loadContentQualityForDoc,
  toErrorMessage: errorMessage,
})

const loadPipelineStatus = async () => {
  await refreshPipelineStatus()
}

const loadPipelineFanout = async () => {
  await refreshPipelineFanout()
}

const reloadPipelineFanout = async () => {
  await loadPipelineFanout()
}

const {
  docOpsMessage,
  docCleanupClearFirst,
  resetConfirmOpen,
  continueQueuedWaiting,
  continueQueuedExpireAt,
  operationActions,
  enqueueDocTask,
  retryTaskRun,
  runDocCleanup,
  runContinuePipeline,
  openResetConfirm,
  confirmResetAndReprocessDoc,
} = useDocumentDetailOperations({
  docId: id,
  enqueueDocumentTaskNow,
  cleanupDocumentTexts,
  continuePipelineRequest,
  resetAndReprocessNow,
  load,
  refreshTaskRuns,
  loadPipelineStatus,
  refreshPipelineFanout,
  toErrorMessage: errorMessage,
})
const {
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
} = useDocumentProcessingState(
  {
    pipelineStatus,
    pipelineFanout,
    taskRuns,
    continueQueuedWaiting,
  },
  checkpointLabel,
)

const reloadAll = async () => {
  reloadingAll.value = true
  try {
    await load()
    await loadMetaForDoc()
    await loadContentQualityForDoc()
    await loadPageTextsForDoc()
    await loadSuggestionsForDoc()
    await loadPipelineStatus()
    await loadPipelineFanout()
  } finally {
    reloadingAll.value = false
  }
}

const {
  writebackRunning,
  writebackConfirmOpen,
  writebackConflictOpen,
  writebackConflicts,
  writebackResolutions,
  writebackErrorOpen,
  writebackErrorMessage,
  canWriteback,
  writebackButtonTitle,
  writebackButtonLabel,
  openWritebackConfirm,
  closeWritebackConfirm,
  confirmWritebackNow,
  cancelWritebackConflict,
  applyWritebackConflictResolutions,
  setConflictResolution,
  closeWritebackError,
} = useDocumentWriteback({
  docId: id,
  document,
  reloadAll: async () => reloadAll(),
  toErrorMessage: errorMessage,
  pushToast: (message, level, title, timeoutMs) =>
    toastStore.push(message, level, title, timeoutMs),
})

const refreshSuggestionsAction = async (source: 'paperless_ocr' | 'vision_ocr') => {
  await refreshSuggestionsForSource(id, source)
}

useAutoRefresh({
  enabled: shouldAutoRefreshTimeline,
  intervalMs: 5000,
  onTick: async () => {
    if (continueQueuedWaiting.value && continueQueuedExpireAt.value > 0 && Date.now() >= continueQueuedExpireAt.value) {
      continueQueuedWaiting.value = false
      continueQueuedExpireAt.value = 0
    }
    await refreshTaskRuns()
    await loadPipelineStatus()
    await refreshPipelineFanout()
  },
})

watch(
  activeRun,
  (run) => {
    if (run && continueQueuedWaiting.value) {
      continueQueuedWaiting.value = false
      continueQueuedExpireAt.value = 0
    }
  },
)

onMounted(async () => {
  syncTabFromQuery()
  syncPdfFromQuery()
  await reloadAll()
})

watch(
  () => route.query,
  () => {
    syncTabFromQuery()
    syncPdfFromQuery()
  },
)

watch(
  activeTab,
  async () => {
    await syncTabToQuery()
  },
)

</script>
