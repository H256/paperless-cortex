<template>
  <section>
    <DocumentDetailHeader
      :title="document?.title || ''"
      :doc-id="docId"
      :header-meta-line="headerMetaLine"
      :active-run-label="activeRunLabel"
      :paperless-url="paperlessUrl"
      :review-marking="reviewMarking"
      :can-mark-reviewed="canMarkReviewed"
      :writeback-running="writebackRunning"
      :can-writeback="canWriteback"
      :writeback-button-title="writebackButtonTitle"
      :writeback-button-label="writebackButtonLabel"
      :reloading-all="reloadingAll"
      @back="navigateBackToDocuments"
      @mark-reviewed="markReviewedAction"
      @open-writeback-confirm="openWritebackConfirm"
      @reload="reloadAll"
    />

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
        @apply-variant="applyVariantAction"
        @apply-variant-to-document="applyVariantToDocumentAction"
        @apply-to-document="applyToDocument"
      />

      <DocumentChatSection v-if="activeTab === 'chat'" :doc-id="docId" />
      <DocumentSimilarSection
        v-if="activeTab === 'similar'"
        :similar-matches="similarMatches"
        :duplicate-matches="duplicateMatches"
        :loading="similarLoading"
        :error="similarError"
        :similar-min-score="similarMinScore"
        :duplicate-threshold="duplicateThreshold"
        :paperless-base-url="paperlessBaseUrl"
        @refresh="loadSimilarity({ similarMinScore, duplicateThreshold })"
        @open-doc="openSimilarDoc"
        @update:similar-min-score="similarMinScore = $event"
        @update:duplicate-threshold="duplicateThreshold = $event"
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
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import DocumentDetailHeader from '../components/DocumentDetailHeader.vue'
import DocumentMetadataSection from '../components/DocumentMetadataSection.vue'
import DocumentTextQualitySection from '../components/DocumentTextQualitySection.vue'
import DocumentSuggestionsSection from '../components/DocumentSuggestionsSection.vue'
import DocumentChatSection from '../components/DocumentChatSection.vue'
import DocumentSimilarSection from '../components/DocumentSimilarSection.vue'
import DocumentPagesSection from '../components/DocumentPagesSection.vue'
import DocumentOperationsSection from '../components/DocumentOperationsSection.vue'
import WritebackConflictModal from '../components/WritebackConflictModal.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import PdfViewer from '../components/PdfViewer.vue'
import { useToastStore } from '../stores/toastStore'
import { useDocumentPipeline } from '../composables/useDocumentPipeline'
import { useDocumentOperations } from '../composables/useDocumentOperations'
import { useDocumentDetailData } from '../composables/useDocumentDetailData'
import { useDocumentSimilarity } from '../composables/useDocumentSimilarity'
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
const docId = computed(() => Number(route.params.id))
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
  similarMatches,
  duplicateMatches,
  loading: similarLoading,
  error: similarError,
  reset: resetSimilarity,
  loadSimilarity,
} = useDocumentSimilarity(() => docId.value)
const similarMinScore = ref(0.5)
const duplicateThreshold = ref(0.92)
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
} = useDocumentPipeline(docId)
const {
  loading: docOpsLoading,
  enqueueTask: enqueueDocumentTaskNow,
  cleanup: cleanupDocumentTexts,
  resetAndReprocess: resetAndReprocessNow,
} = useDocumentOperations(docId)
const timelineStatusFilter = ref('')
const timelineQueryFilter = ref('')
const {
  taskRuns,
  taskRunsLoading,
  taskRunsError,
  refreshTaskRuns,
} = useDocumentTaskRuns(() => docId.value, {
  status: timelineStatusFilter,
  query: timelineQueryFilter,
})

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || '/api'
const pdfUrl = computed(() => `${apiBaseUrl}/documents/${docId.value}/pdf`)
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

const suggestFieldAction = async (source: 'paperless_ocr' | 'vision_ocr' | 'similar_docs', field: string) => {
  if (source === 'similar_docs') return
  await suggestField(docId.value, source, field)
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
const { reviewMarking, markReviewed } = useDocumentReview(docId)

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
  return `Document ID: ${docId.value}, Synced at: ${syncAt || '-'}, ${reviewPart || 'Unknown'}`
})

const navigateBackToDocuments = async () => {
  await router.push(returnToDocumentsPath.value)
}

const openSimilarDoc = async (docId: number) => {
  if (!docId) return
  const returnTo = encodeURIComponent(returnToDocumentsPath.value)
  await router.push(`/documents/${docId}?return_to=${returnTo}`)
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
  await loadDocument(docId.value)
}

const loadMetaForDoc = async () => {
  await loadMeta()
}

const loadPageTextsForDoc = async (priority = false) => {
  await loadPageTexts(docId.value, priority)
}

const loadContentQualityForDoc = async (priority = false) => {
  await loadContentQuality(docId.value, priority)
  await loadOcrScores(docId.value, priority)
}

const loadSuggestionsForDoc = async () => {
  await loadSuggestions(docId.value)
}

const {
  applyVariantOnly,
  applyVariantToDocument,
  applyToDocument,
} = useDocumentSuggestionsApply({
  docId: () => docId.value,
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

const applyVariantAction = async (
  source: 'paperless_ocr' | 'vision_ocr' | 'similar_docs',
  field: string,
  value: unknown,
) => {
  if (source === 'similar_docs') return
  await applyVariantOnly(source, field, value)
}

const applyVariantToDocumentAction = async (
  source: 'paperless_ocr' | 'vision_ocr' | 'similar_docs',
  field: string,
  value: unknown,
) => {
  if (source === 'similar_docs') return
  await applyVariantToDocument(source, field, value)
}

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
  docId: () => docId.value,
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
    resetSimilarity()
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
  docId: () => docId.value,
  document,
  reloadAll: async () => reloadAll(),
  toErrorMessage: errorMessage,
  pushToast: (message, level, title, timeoutMs) =>
    toastStore.push(message, level, title, timeoutMs),
})

const refreshSuggestionsAction = async (source: 'paperless_ocr' | 'vision_ocr' | 'similar_docs') => {
  if (source === 'similar_docs') {
    await loadSuggestionsForDoc()
    return
  }
  await refreshSuggestionsForSource(docId.value, source)
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
  () => route.params.id,
  async (next, prev) => {
    if (String(next) === String(prev)) return
    resetSimilarity()
    await reloadAll()
  },
)

watch(
  activeTab,
  async (tab) => {
    await syncTabToQuery()
    if (tab === 'similar') {
      await loadSimilarity({
        similarMinScore: similarMinScore.value,
        duplicateThreshold: duplicateThreshold.value,
      })
    }
  },
)

let similarityReloadTimer: ReturnType<typeof setTimeout> | null = null
watch([similarMinScore, duplicateThreshold, activeTab], ([minScore, dupThreshold, tab]) => {
  if (tab !== 'similar') return
  if (similarityReloadTimer) {
    clearTimeout(similarityReloadTimer)
  }
  similarityReloadTimer = setTimeout(() => {
    loadSimilarity({
      similarMinScore: minScore,
      duplicateThreshold: dupThreshold,
    })
  }, 250)
})
onBeforeUnmount(() => {
  if (similarityReloadTimer) {
    clearTimeout(similarityReloadTimer)
    similarityReloadTimer = null
  }
})

</script>
