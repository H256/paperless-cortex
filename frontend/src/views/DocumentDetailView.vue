<template>
  <section>
    <div class="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h2 class="text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">
          {{ document?.title || `Document ${id}` }}
        </h2>
        <p class="text-sm text-slate-500 dark:text-slate-400">Document ID: {{ id }}</p>
      </div>
      <div class="flex items-center gap-2">
        <IconButton
          v-if="paperlessUrl"
          :href="paperlessUrl"
          title="View document in Paperless"
          aria-label="View document in Paperless"
        >
          <ExternalLink class="h-5 w-5" />
        </IconButton>
        <IconButton
          v-else
          disabled
          title="Set VITE_PAPERLESS_BASE_URL to enable"
          aria-label="Paperless link unavailable"
        >
          <ExternalLink class="h-5 w-5" />
        </IconButton>
        <button
          class="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-slate-800"
          @click="load"
        >
          <RefreshCw class="h-4 w-4" />
          Reload
        </button>
      </div>
    </div>

    <section
      class="mt-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900"
    >
      <div class="flex flex-wrap items-center gap-3">
        <div
          class="flex flex-wrap items-center gap-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-600 dark:border-slate-800 dark:bg-slate-800 dark:text-slate-300"
        >
          <label class="inline-flex items-center gap-2">
            <input type="checkbox" v-model="doResync" />
            Resync
          </label>
          <label class="inline-flex items-center gap-2">
            <input type="checkbox" v-model="doReembed" :disabled="!doResync" />
            Re-embed
          </label>
          <label class="inline-flex items-center gap-2">
            <input type="checkbox" v-model="doQuality" />
            Analyze quality
          </label>
          <label class="inline-flex items-center gap-2">
            <input type="checkbox" v-model="doPages" />
            Load extracted pages
          </label>
          <label class="inline-flex items-center gap-2">
            <input type="checkbox" v-model="doSuggestions" />
            Generate suggestions
          </label>
        </div>
        <button
          class="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500"
          :disabled="processing"
          @click="runReprocess"
        >
          <RefreshCcw class="h-4 w-4" />
          {{ processing ? 'Processing...' : 'Re-process' }}
        </button>
      </div>
    </section>

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
        :page-texts-error="pageTextsError"
        :aggregated-text="aggregatedText"
        :pdf-url="pdfUrl"
        :pdf-page="pdfPage"
        :pdf-highlights="pdfHighlights"
        @update:page="onPdfPageChange"
      />

    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ExternalLink, RefreshCcw, RefreshCw } from 'lucide-vue-next'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import IconButton from '../components/IconButton.vue'
import DocumentMetadataSection from '../components/DocumentMetadataSection.vue'
import DocumentTextQualitySection from '../components/DocumentTextQualitySection.vue'
import DocumentSuggestionsSection from '../components/DocumentSuggestionsSection.vue'
import DocumentPagesSection from '../components/DocumentPagesSection.vue'
import { useDocumentDetailStore } from '../stores/documentDetailStore'
import { useQueueStore } from '../stores/queueStore'
import { useToastStore } from '../stores/toastStore'
import { useStatusStore } from '../stores/statusStore'

const route = useRoute()
const router = useRouter()
const id = Number(route.params.id)

const documentStore = useDocumentDetailStore()
const queueStore = useQueueStore()
const toastStore = useToastStore()
const statusStore = useStatusStore()
const {
  document,
  loading,
  tags,
  correspondents,
  docTypes,
  pageTexts,
  pageTextsError,
  contentQuality,
  contentQualityError,
  suggestions,
  suggestionsLoading,
  suggestionsError,
  suggestionVariants,
  suggestionVariantLoading,
  suggestionVariantError,
} = storeToRefs(documentStore)

const processing = ref(false)
const doResync = ref(true)
const doReembed = ref(true)
const doQuality = ref(true)
const doPages = ref(true)
const doSuggestions = ref(true)
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || '/api'
const pdfUrl = computed(() => `${apiBaseUrl}/documents/${id}/pdf`)
const pdfPage = ref(1)
const pdfHighlights = ref<number[][]>([])
const tabs = [
  { key: 'meta', label: 'Metadata' },
  { key: 'text', label: 'Text & quality' },
  { key: 'suggestions', label: 'Suggestions' },
  { key: 'pages', label: 'Pages' },
]
const activeTab = ref('meta')

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
  date: formatDate(document.value?.document_date) || '',
  correspondent: currentCorrespondentName.value || '',
  tags: currentTagNames.value || '',
  note: currentNotePreview.value || '',
}))

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
  return [
    { label: 'ID', value: document.value.id },
    { label: 'Title', value: document.value.title },
    { label: 'Document date', value: formatDate(document.value.document_date) },
    { label: 'Created', value: formatDateTime(document.value.created) },
    { label: 'Modified', value: formatDateTime(document.value.modified) },
    { label: 'Correspondent', value: correspondentName },
    { label: 'Document type', value: docTypeName },
    { label: 'Tags', value: tagNames },
    { label: 'Original filename', value: document.value.original_file_name },
    { label: 'Notes', value: notes },
  ]
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

const resync = async () => {
  await documentStore.resync(id, doReembed.value)
}

const loadMeta = async () => {
  await documentStore.loadMeta()
}

const loadPageTexts = async (priority = false) => {
  await documentStore.loadPageTexts(id, priority)
}

const loadContentQuality = async (priority = false) => {
  await documentStore.loadContentQuality(id, priority)
}

const loadSuggestions = async () => {
  await documentStore.loadSuggestions(id)
}

const refreshSuggestions = async (source: 'paperless_ocr' | 'vision_ocr') => {
  await documentStore.refreshSuggestions(id, source)
}

const runReprocess = async () => {
  processing.value = true
  try {
    if (doResync.value) {
      await resync()
      await queueStore.refreshStatus()
      if (queueStore.status.enabled) {
        toastStore.push(`Document ${id} queued for processing.`, 'info', 'Queued')
      }
    }
    if (doQuality.value) {
      await loadContentQuality(true)
    }
    if (doPages.value) {
      await loadPageTexts(true)
    }
    if (doSuggestions.value) {
      await loadSuggestions()
    }
  } finally {
    processing.value = false
  }
}


onMounted(async () => {
  syncPdfFromQuery()
  await load()
  await loadMeta()
  if (doQuality.value) {
    await loadContentQuality()
  }
  if (doPages.value) {
    await loadPageTexts()
  }
  if (doSuggestions.value) {
    await loadSuggestions()
  }
})

watch(
  () => route.query,
  () => {
    syncPdfFromQuery()
  },
)

watch(doPages, async (value) => {
  if (value && pageTexts.value.length === 0) {
    await loadPageTexts()
  }
})
</script>
