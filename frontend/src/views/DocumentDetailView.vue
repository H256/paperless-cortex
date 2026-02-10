<template>
  <section>
    <div class="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h2 class="text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">
          {{ document?.title || `Document ${id}` }}
        </h2>
        <p class="text-sm text-slate-500 dark:text-slate-400">{{ headerMetaLine }}</p>
      </div>
      <div class="flex items-center gap-2">
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
          class="inline-flex items-center gap-2 rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-2 text-sm font-semibold text-indigo-700 shadow-sm hover:border-indigo-300 dark:border-indigo-900/50 dark:bg-indigo-950/30 dark:text-indigo-200"
          :disabled="writebackRunning || !canWriteback"
          :class="writebackRunning || !canWriteback ? 'cursor-not-allowed opacity-70' : ''"
          :title="canWriteback ? 'Write local changes back to Paperless' : 'Writeback is only available when status is Needs review'"
          @click="openWritebackConfirm"
        >
          <ClipboardCheck class="h-4 w-4" :class="writebackRunning ? 'animate-pulse' : ''" />
          {{ writebackRunning ? 'Writing back...' : 'Write back to Paperless' }}
        </button>
        <button
          class="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-slate-800"
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
      <div
        class="flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white p-2 text-xs font-semibold text-slate-600 shadow-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
      >
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
        @refresh="refreshSuggestions"
        @suggest-field="suggestField"
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

      <section
        v-if="activeTab === 'operations'"
        class="space-y-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900"
      >
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 class="text-lg font-semibold text-slate-900 dark:text-slate-100">Document operations</h3>
            <p class="text-xs text-slate-500 dark:text-slate-400">
              Trigger single processing steps or fully reset and rebuild this document.
            </p>
          </div>
        </div>

        <div class="rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-slate-800 dark:bg-slate-800">
          <label class="inline-flex items-center gap-2 text-xs text-slate-500 dark:text-slate-300">
            <input type="checkbox" v-model="docCleanupClearFirst" />
            Clear clean fields first
          </label>
          <div class="mt-2">
            <button
              class="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
              :disabled="docOpsLoading"
              title="Cleans stored page texts (e.g., line wraps or HTML noise) and updates clean fields."
              @click="runDocCleanup"
            >
              Cleanup page texts (this doc)
            </button>
          </div>
        </div>

        <div class="grid gap-2 md:grid-cols-2">
          <button
            v-for="action in operationActions"
            :key="action.task"
            class="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
            :disabled="docOpsLoading"
            :title="action.tooltip"
            @click="enqueueDocTask(action)"
          >
            {{ action.label }}
          </button>
        </div>

        <div class="rounded-lg border border-rose-200 bg-rose-50 p-3 dark:border-rose-900/50 dark:bg-rose-950/40">
          <button
            class="rounded-lg bg-rose-600 px-3 py-2 text-xs font-semibold text-white hover:bg-rose-500"
            :disabled="docOpsLoading"
            title="Deletes local intelligence data for this document, resyncs from Paperless, and enqueues processing."
            @click="openResetConfirm"
          >
            Reset document + sync + full reprocess
          </button>
          <p class="mt-2 text-xs text-rose-700 dark:text-rose-200">
            Deletes local intelligence for this document, syncs from Paperless, then enqueues full processing.
          </p>
        </div>

        <div v-if="docOpsMessage" class="text-xs text-slate-500 dark:text-slate-300">
          {{ docOpsMessage }}
        </div>
      </section>

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
        @cancel="writebackConfirmOpen = false"
      />
      <div
        v-if="writebackConflictOpen"
        class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 px-4"
      >
        <div
          class="w-full max-w-3xl rounded-xl border border-slate-200 bg-white p-5 shadow-xl dark:border-slate-700 dark:bg-slate-900"
        >
          <div class="text-base font-semibold text-slate-900 dark:text-slate-100">
            Resolve writeback conflicts
          </div>
          <p class="mt-2 text-sm text-slate-600 dark:text-slate-300">
            Paperless changed since this document was loaded. Choose how each field should be handled.
          </p>
          <div class="mt-4 space-y-3">
            <div
              v-for="conflict in writebackConflicts"
              :key="conflict.field"
              class="rounded-lg border border-slate-200 p-3 dark:border-slate-700"
            >
              <div class="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                {{ conflictFieldLabel(conflict.field) }}
              </div>
              <div class="mt-2 grid gap-3 md:grid-cols-2">
                <div>
                  <div class="text-[11px] font-semibold text-slate-500 dark:text-slate-400">Paperless</div>
                  <div class="mt-1 whitespace-pre-wrap rounded-md bg-slate-50 p-2 text-xs text-slate-700 dark:bg-slate-800 dark:text-slate-200">
                    {{ conflictValue(conflict.paperless) }}
                  </div>
                </div>
                <div>
                  <div class="text-[11px] font-semibold text-slate-500 dark:text-slate-400">Local</div>
                  <div class="mt-1 whitespace-pre-wrap rounded-md bg-slate-50 p-2 text-xs text-slate-700 dark:bg-slate-800 dark:text-slate-200">
                    {{ conflictValue(conflict.local) }}
                  </div>
                </div>
              </div>
              <div class="mt-3">
                <select
                  v-model="writebackResolutions[conflict.field]"
                  class="w-full rounded-lg border border-slate-200 bg-white px-2 py-2 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                >
                  <option value="skip">Skip</option>
                  <option value="use_paperless">Use Paperless (sync local)</option>
                  <option value="use_local">Use Local (writeback)</option>
                </select>
              </div>
            </div>
          </div>
          <div class="mt-4 flex justify-end gap-2">
            <button
              class="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-slate-500"
              @click="cancelWritebackConflict"
            >
              Cancel
            </button>
            <button
              class="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-sm font-semibold text-emerald-700 hover:border-emerald-300 dark:border-emerald-900/50 dark:bg-emerald-950/40 dark:text-emerald-200"
              :disabled="writebackRunning"
              @click="applyWritebackConflictResolutions"
            >
              Apply decisions
            </button>
          </div>
        </div>
      </div>
      <ConfirmDialog
        :open="writebackErrorOpen"
        title="Writeback failed"
        :message="writebackErrorMessage || 'Unknown error'"
        confirm-label="Close"
        cancel-label="Close"
        @confirm="writebackErrorOpen = false"
        @cancel="writebackErrorOpen = false"
      />

    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ClipboardCheck, ExternalLink, RefreshCw } from 'lucide-vue-next'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import IconButton from '../components/IconButton.vue'
import DocumentMetadataSection from '../components/DocumentMetadataSection.vue'
import DocumentTextQualitySection from '../components/DocumentTextQualitySection.vue'
import DocumentSuggestionsSection from '../components/DocumentSuggestionsSection.vue'
import DocumentPagesSection from '../components/DocumentPagesSection.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import PdfViewer from '../components/PdfViewer.vue'
import { useDocumentDetailStore } from '../stores/documentDetailStore'
import { useQueueStore } from '../stores/queueStore'
import { useStatusStore } from '../stores/statusStore'
import { useToastStore } from '../stores/toastStore'
import { cleanupTexts, enqueueDocumentTask, resetAndReprocessDocument } from '../services/documents'
import type { DocumentOperationTaskPayload } from '../services/documents'
import { executeWritebackDirectForDocument, type WritebackConflictField } from '../services/writeback'

const route = useRoute()
const router = useRouter()
const id = Number(route.params.id)

const documentStore = useDocumentDetailStore()
const queueStore = useQueueStore()
const statusStore = useStatusStore()
const toastStore = useToastStore()
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
} = storeToRefs(documentStore)

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || '/api'
const pdfUrl = computed(() => `${apiBaseUrl}/documents/${id}/pdf`)
const pdfPage = ref(1)
const pdfHighlights = ref<number[][]>([])
const tabs = [
  { key: 'meta', label: 'Metadata' },
  { key: 'text', label: 'Text & quality' },
  { key: 'suggestions', label: 'Suggestions' },
  { key: 'pages', label: 'Pages' },
  { key: 'operations', label: 'Operations' },
]
type OperationAction = {
  task: Extract<
    DocumentOperationTaskPayload['task'],
    | 'vision_ocr'
    | 'embeddings_vision'
    | 'page_notes_vision'
    | 'summary_hierarchical'
    | 'suggestions_paperless'
    | 'suggestions_vision'
  >
  label: string
  tooltip: string
  force?: boolean
  source?: 'paperless_ocr' | 'vision_ocr'
}

const operationActions: OperationAction[] = [
  {
    task: 'vision_ocr',
    label: 'Queue vision OCR',
    tooltip: 'Triggers vision OCR again for pages of this document.',
    force: true,
  },
  {
    task: 'embeddings_vision',
    label: 'Queue embeddings (vision)',
    tooltip: 'Erstellt Embeddings aus Vision-OCR-Text und speichert sie in Qdrant.',
  },
  {
    task: 'page_notes_vision',
    label: 'Queue page notes (vision)',
    tooltip: 'Generates structured page notes from vision OCR per page.',
  },
  {
    task: 'summary_hierarchical',
    label: 'Queue hierarchical summary',
    tooltip: 'Aggregates page notes by section and builds a hierarchical summary.',
    source: 'vision_ocr',
  },
  {
    task: 'suggestions_paperless',
    label: 'Queue suggestions (paperless)',
    tooltip: 'Generates suggestion fields from Paperless OCR text.',
  },
  {
    task: 'suggestions_vision',
    label: 'Queue suggestions (vision)',
    tooltip: 'Generates suggestion fields from vision OCR text.',
  },
]
const activeTab = ref('meta')
const reloadingAll = ref(false)
const docOpsLoading = ref(false)
const docCleanupClearFirst = ref(false)
const docOpsMessage = ref('')
const resetConfirmOpen = ref(false)
const writebackRunning = ref(false)
const writebackConfirmOpen = ref(false)
const writebackConflictOpen = ref(false)
const writebackConflicts = ref<WritebackConflictField[]>([])
const writebackResolutions = ref<Record<string, 'skip' | 'use_paperless' | 'use_local'>>({})
const writebackErrorOpen = ref(false)
const writebackErrorMessage = ref('')
const canWriteback = computed(() => document.value?.review_status === 'needs_review')

const parseBBox = (value: unknown): number[] | null => {
  if (!value) return null
  const raw = Array.isArray(value) ? value[0] : value
  if (typeof raw !== 'string') return null
  const parts = raw.split(',').map((part) => Number(part.trim()))
  if (parts.length !== 4 || parts.some((v) => Number.isNaN(v))) return null
  return parts as number[]
}

const paperlessBaseUrl = computed(
  () => import.meta.env.VITE_PAPERLESS_BASE_URL || statusStore.paperlessBaseUrl || '',
)
const paperlessUrl = computed(() =>
  paperlessBaseUrl.value && document.value
    ? `${paperlessBaseUrl.value.replace(/\/$/, '')}/documents/${document.value.id}`
    : '',
)

const errorMessage = (err: unknown, fallback: string) => {
  if (err instanceof Error) return err.message || fallback
  if (typeof err === 'string') return err || fallback
  return fallback
}

const aggregatedText = computed(() => {
  if (!pageTexts.value.length) return document.value?.content || ''
  return pageTexts.value.map((page) => page.text).join('\n\n')
})

const suggestField = async (source: 'paperless_ocr' | 'vision_ocr', field: string) => {
  await documentStore.suggestField(id, source, field)
}

const applyVariantOnly = async (
  source: 'paperless_ocr' | 'vision_ocr',
  field: string,
  value: unknown,
) => {
  await documentStore.applyVariant(id, source, field, value)
}

const applyVariantToDocument = async (
  source: 'paperless_ocr' | 'vision_ocr',
  field: string,
  value: unknown,
) => {
  await documentStore.applyVariant(id, source, field, value)
  await documentStore.applyToDocument(id, { source, field, value })
  await load()
  await loadSuggestions()
}

const applyToDocument = async (source: string, field: string, value: unknown) => {
  try {
    const reloadSuggestions = Boolean(suggestions.value)
    const reloadPages = pageTexts.value.length > 0
    const reloadQuality = Boolean(contentQuality.value)
    await documentStore.applyToDocument(id, { source, field, value })
    await load()
    if (reloadSuggestions) {
      await loadSuggestions()
    }
    if (reloadPages) {
      await loadPageTexts()
    }
    if (reloadQuality) {
      await loadContentQuality()
    }
  } catch (err: unknown) {
    suggestionsError.value = errorMessage(err, 'Failed to apply suggestion to document')
  }
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
  return (
    document.value.correspondent_name ??
    correspondents.value.find((c) => c.id === document.value?.correspondent)?.name ??
    document.value.correspondent ??
    ''
  )
})

const currentValues = computed(() => ({
  title: document.value?.title || '',
  date: formatDate(document.value?.document_date || document.value?.created) || '',
  correspondent: currentCorrespondentName.value || '',
  tags: currentTagNames.value || '',
  note: currentNotePreview.value || '',
}))

const toTitle = (value: string | null | undefined) => {
  if (!value) return 'Unknown'
  return value
    .split('_')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

const rows = computed(() => {
  if (!document.value) return []
  const notes = (document.value.notes || []).map((n) => n.note).join(' ')
  const tagNames = (document.value.tags || [])
    .map((tagId) => tags.value.find((t) => t.id === tagId)?.name ?? tagId)
    .join(', ')
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
    { label: 'Issue date', value: formatDate(document.value.document_date || document.value.created) },
    { label: 'Correspondent', value: correspondentName },
    { label: 'Document type', value: docTypeName },
    { label: 'Tags', value: tagNames },
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

const syncPdfFromQuery = () => {
  const pageValue = Number(route.query.page)
  if (Number.isFinite(pageValue) && pageValue > 0) {
    pdfPage.value = pageValue
  }
  const bbox = parseBBox(route.query.bbox)
  pdfHighlights.value = bbox ? [bbox] : []
}

const onPdfPageChange = (value: number) => {
  pdfPage.value = value
  const nextQuery: Record<string, string> = {}
  Object.entries(route.query).forEach(([key, val]) => {
    if (val === undefined || val === null) return
    const entry = Array.isArray(val) ? val[0] : val
    if (typeof entry === 'string') {
      nextQuery[key] = entry
    }
  })
  nextQuery.page = String(value)
  delete nextQuery.bbox
  router.replace({ query: nextQuery })
  pdfHighlights.value = []
}

const conflictFieldLabel = (field: string) => {
  if (field === 'issue_date' || field === 'document_date') return 'Issue date'
  if (field === 'title') return 'Title'
  if (field === 'correspondent') return 'Correspondent'
  if (field === 'tags') return 'Tags'
  if (field === 'note') return 'Note'
  return field
}

const conflictValue = (value: unknown) => {
  if (value === null || value === undefined || value === '') return '-'
  if (typeof value === 'string') return value
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

const runWritebackNowForDocument = async (
  resolutions?: Record<string, 'skip' | 'use_paperless' | 'use_local'>,
) => {
  writebackRunning.value = true
  writebackErrorMessage.value = ''
  try {
    const result = await executeWritebackDirectForDocument(id, {
      known_paperless_modified: document.value?.paperless_modified ?? null,
      resolutions: resolutions ?? {},
    })
    if (result.status === 'conflicts') {
      writebackConflicts.value = result.conflicts || []
      writebackResolutions.value = Object.fromEntries(
        writebackConflicts.value.map((conflict) => [conflict.field, 'skip']),
      ) as Record<string, 'skip' | 'use_paperless' | 'use_local'>
      writebackConflictOpen.value = true
      toastStore.push(
        'Conflicts detected. Choose per field how to proceed.',
        'warning',
        'Writeback',
        3000,
      )
      return
    }
    const calls = result.calls_count ?? 0
    const changed = result.docs_changed ?? 0
    if (calls > 0 && changed > 0) {
      toastStore.push(
        `Writeback executed ${calls} call(s) for ${changed} changed document(s).`,
        'success',
        'Writeback',
        2200,
      )
    } else {
      toastStore.push(
        'No writeback changes found for this document.',
        'info',
        'Writeback',
        2200,
      )
    }
    await reloadAll()
  } catch (err: unknown) {
    const message = errorMessage(err, 'Failed to write back document')
    toastStore.push(message, 'danger', 'Writeback', 2800)
    writebackErrorMessage.value = message
    writebackErrorOpen.value = true
  } finally {
    writebackRunning.value = false
  }
}

const openWritebackConfirm = () => {
  if (!canWriteback.value || writebackRunning.value) return
  writebackConfirmOpen.value = true
}

const confirmWritebackNow = async () => {
  writebackConfirmOpen.value = false
  await runWritebackNowForDocument()
}

const cancelWritebackConflict = () => {
  writebackConflictOpen.value = false
  writebackConflicts.value = []
  writebackResolutions.value = {}
}

const applyWritebackConflictResolutions = async () => {
  writebackConflictOpen.value = false
  await runWritebackNowForDocument({ ...writebackResolutions.value })
  writebackConflicts.value = []
  writebackResolutions.value = {}
}

const formatDate = (value?: string | null) => {
  if (!value) return ''
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return new Intl.DateTimeFormat(navigator.language).format(parsed)
}

const formatDateTime = (value?: string | null) => {
  if (!value) return ''
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return new Intl.DateTimeFormat(navigator.language, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(parsed)
}

const load = async () => {
  await documentStore.loadDocument(id)
}

const loadMeta = async () => {
  await documentStore.loadMeta()
}

const loadPageTexts = async (priority = false) => {
  await documentStore.loadPageTexts(id, priority)
}

const loadContentQuality = async (priority = false) => {
  await documentStore.loadContentQuality(id, priority)
  await documentStore.loadOcrScores(id, priority)
}

const loadSuggestions = async () => {
  await documentStore.loadSuggestions(id)
}

const withDocOperation = async (fn: () => Promise<void>) => {
  docOpsLoading.value = true
  docOpsMessage.value = ''
  try {
    await fn()
    await queueStore.refreshStatus()
  } finally {
    docOpsLoading.value = false
  }
}

const reloadAll = async () => {
  reloadingAll.value = true
  try {
    await load()
    await loadMeta()
    await loadContentQuality()
    await loadPageTexts()
    await loadSuggestions()
  } finally {
    reloadingAll.value = false
  }
}

const refreshSuggestions = async (source: 'paperless_ocr' | 'vision_ocr') => {
  await documentStore.refreshSuggestions(id, source)
}

const enqueueDocTask = async (action: OperationAction) => {
  await withDocOperation(async () => {
    try {
      const result = await enqueueDocumentTask(id, {
        task: action.task,
        force: action.force ?? false,
        source: action.source,
      })
      docOpsMessage.value = result.enqueued
        ? `Queued task ${action.task} for document ${id}.`
        : `Task ${action.task} was not enqueued (possibly duplicate/running).`
    } catch (err) {
      docOpsMessage.value = errorMessage(err, `Failed to queue ${action.task}`)
    }
  })
}

const runDocCleanup = async () => {
  await withDocOperation(async () => {
    try {
      const result = await cleanupTexts({
        doc_ids: [id],
        clear_first: docCleanupClearFirst.value,
        enqueue: true,
      })
      docOpsMessage.value = result.queued
        ? `Queued cleanup for ${result.docs} document(s).`
        : `Cleanup done: ${result.updated}/${result.processed} updated.`
    } catch (err) {
      docOpsMessage.value = errorMessage(err, 'Failed to queue cleanup')
    }
  })
}

const runResetAndReprocessDoc = async () => {
  await withDocOperation(async () => {
    try {
      const result = await resetAndReprocessDocument(id, true)
      docOpsMessage.value = `Document reset/synced. Enqueued ${result.enqueued} tasks.`
      await load()
    } catch (err) {
      docOpsMessage.value = errorMessage(err, 'Failed to reset and reprocess document')
    }
  })
}

const openResetConfirm = () => {
  resetConfirmOpen.value = true
}

const confirmResetAndReprocessDoc = async () => {
  resetConfirmOpen.value = false
  await runResetAndReprocessDoc()
}


onMounted(async () => {
  syncPdfFromQuery()
  await reloadAll()
})

watch(
  () => route.query,
  () => {
    syncPdfFromQuery()
  },
)

</script>
