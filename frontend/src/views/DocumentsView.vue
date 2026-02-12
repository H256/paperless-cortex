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

    <section
      class="mt-6 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900"
    >
      <div>
        <table class="w-full border-collapse text-sm">
          <thead
            class="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500 dark:bg-slate-800 dark:text-slate-400"
          >
            <tr>
              <th class="px-6 py-3">
                <button
                  class="inline-flex items-center gap-1"
                  type="button"
                  @click.stop="toggleSort('title')"
                >
                  Title
                  <ChevronDown
                    v-if="sortDir('title')"
                    class="h-3 w-3 text-slate-400"
                    :class="{ 'rotate-180': sortDir('title') === 'desc' }"
                  />
                </button>
              </th>
              <th class="px-6 py-3">
                <button
                  class="inline-flex items-center gap-1"
                  type="button"
                  @click.stop="toggleSort('date')"
                >
                  Issue date
                  <ChevronDown
                    v-if="sortDir('date')"
                    class="h-3 w-3 text-slate-400"
                    :class="{ 'rotate-180': sortDir('date') === 'desc' }"
                  />
                </button>
              </th>
              <th class="px-6 py-3">Correspondent</th>
              <th class="px-6 py-3">Source</th>
              <th class="px-6 py-3">Links</th>
              <th class="px-6 py-3">Status</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="doc in visibleDocuments"
              :key="doc.id ?? `${doc.title}-${doc.created ?? ''}`"
              class="border-b border-slate-100 hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-800"
              @click="openDoc(doc)"
            >
              <td class="px-6 py-3 text-slate-900 dark:text-slate-100">{{ doc.title }}</td>
              <td class="px-6 py-3 text-slate-600">
                {{ formatDate(doc.document_date || doc.created) }}
              </td>
              <td class="px-6 py-3 text-slate-600">
                {{ correspondentLabel(doc.correspondent, doc.correspondent_name) }}
              </td>
              <td class="px-6 py-3">
                <div class="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                  <div
                    class="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-2 py-1 dark:border-slate-700 dark:bg-slate-900"
                    :title="doc.local_cached ? 'Paperless + local cache' : 'Paperless only'"
                  >
                    <Database
                      class="h-3.5 w-3.5"
                      :class="doc.local_cached ? 'text-indigo-600' : 'text-slate-400'"
                    />
                  </div>
                  <div
                    v-if="doc.local_overrides"
                    class="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2 py-1 dark:border-amber-900/50 dark:bg-amber-950/40"
                    title="Local values override Paperless"
                  >
                    <Pencil class="h-3.5 w-3.5 text-amber-600" />
                  </div>
                </div>
              </td>
              <td class="px-6 py-3 text-slate-600">
                <a
                  v-if="paperlessBaseUrl"
                  class="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
                  :href="paperlessDocUrl(doc.id ?? 0)"
                  target="_blank"
                  rel="noopener"
                  @click.stop
                >
                  <ExternalLink class="h-3 w-3" />
                </a>
              </td>
              <td class="px-6 py-3">
                <DocumentProcessingBadges :doc="doc" />
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div
        class="flex items-center justify-between px-6 py-4 text-sm text-slate-600 dark:text-slate-300"
      >
        <button
          class="rounded-lg border border-slate-200 bg-white px-4 py-2 font-semibold text-slate-700 shadow-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
          :disabled="page <= 1"
          @click="page -= 1;load()"
        >
          Prev
        </button>
        <div class="text-center">
          <div class="text-sm font-semibold text-slate-700 dark:text-slate-200">
            Page {{ page }} of {{ totalPages }}
          </div>
          <div class="text-xs text-slate-400 dark:text-slate-500">
            Last synced: {{ formatDateTime(lastSynced) }}
          </div>
        </div>
        <button
          class="rounded-lg border border-slate-200 bg-white px-4 py-2 font-semibold text-slate-700 shadow-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
          :disabled="page >= totalPages"
          @click="            page += 1;            load()          "
        >
          Next
        </button>
      </div>
    </section>
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
  ChevronDown,
  Database,
  ExternalLink,
  Loader2,
  Pencil,
  RefreshCw,
  XCircle,
} from 'lucide-vue-next'
import { useRouter } from 'vue-router'
import { useToastStore } from '../stores/toastStore'
import { useContinueProcessing } from '../composables/useContinueProcessing'
import { useContinueProcessOptions } from '../composables/useContinueProcessOptions'
import { useDocumentsCatalog } from '../composables/useDocumentsCatalog'
import { useProcessingOverview } from '../composables/useProcessingOverview'
import { useProcessingMetrics } from '../composables/useProcessingMetrics'
import { usePaperlessBaseUrl } from '../composables/usePaperlessBaseUrl'
import ContinueProcessingModal from '../components/ContinueProcessingModal.vue'
import DocumentProcessingBadges from '../components/DocumentProcessingBadges.vue'
import DocumentsFiltersPanel from '../components/DocumentsFiltersPanel.vue'
import type { DocumentRow } from '../services/documents'

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

const paperlessDocUrl = (id: number) =>
  paperlessBaseUrl.value ? `${paperlessBaseUrl.value.replace(/\/$/, '')}/documents/${id}` : ''

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

const refreshAfterProcessingMutation = async () => {
  await Promise.all([refreshProcessingOverview(), load()])
}

const openPreview = async () => {
  try {
    await openPreviewRequest(processParams())
    await refreshAfterProcessingMutation()
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to prepare processing preview'
    toastStore.push(message, 'danger', 'Processing')
  }
}

const closePreview = () => {
  clearPreviewState()
}

const startFromPreview = async () => {
  try {
    await startFromPreviewRequest(processParams())
    if (processStartResult.value) {
      toastStore.push(
        `Enqueued ${processStartResult.value.enqueued ?? 0} docs (${processStartResult.value.tasks ?? 0} tasks).`,
        'success',
        'Queue started',
      )
    }
    clearPreviewState()
    await refreshAfterProcessingMutation()
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to start processing'
    toastStore.push(message, 'danger', 'Processing')
  }
}

const cancelProcessing = async () => {
  try {
    await cancelProcessingRequest()
    await clearQueueNow()
    await refreshAfterProcessingMutation()
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to cancel processing'
    toastStore.push(message, 'danger', 'Processing')
  }
}

const open = (id: number) => {
  router.push(`/documents/${id}`)
}

const openDoc = (doc: DocumentRow) => {
  if (typeof doc.id !== 'number') return
  open(doc.id)
}

const correspondentLabel = (id?: number | null, name?: string | null) => {
  if (name) return name
  if (!id) return ''
  return correspondents.value.find((c) => c.id === id)?.name ?? String(id)
}

const hasDerived = (doc: DocumentRow) => {
  return Boolean(doc.has_embeddings || doc.has_suggestions || doc.has_vision_pages)
}

const visibleDocuments = computed(() => {
  let filtered = documents.value
  if (analysisFilter.value !== 'all') {
    const shouldBeAnalyzed = analysisFilter.value === 'analyzed'
    filtered = filtered.filter((doc) => hasDerived(doc) === shouldBeAnalyzed)
  }
  const needle = modelFilter.value.trim().toLowerCase()
  if (!needle) return filtered
  return filtered.filter((doc) =>
    String(doc.analysis_model || '')
      .toLowerCase()
      .includes(needle),
  )
})

const formatDate = (value?: string | null) => {
  if (!value) return ''
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return new Intl.DateTimeFormat(navigator.language).format(parsed)
}

const formatDateTime = (value?: string | null) => {
  if (!value) return 'never'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return new Intl.DateTimeFormat(navigator.language, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(parsed)
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
