<template>
  <div>
    <h2 class="text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">
      Semantic Search
    </h2>
    <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">
      Search across your documents with embeddings and citations.
    </p>

    <section
      class="mt-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900"
    >
      <div class="flex flex-wrap items-end gap-4">
        <div class="flex-1 min-w-[260px]">
          <label class="text-xs font-medium text-slate-600 dark:text-slate-300">Query</label>
          <div class="mt-1 flex items-center gap-2">
            <input
              v-model="query"
              class="h-10 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 text-sm text-slate-900 outline-none focus:border-indigo-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
              type="text"
              placeholder="Ask a question or search..."
              @keyup.enter="runSearchAction"
            />
            <button
              class="inline-flex h-10 items-center gap-2 rounded-lg bg-indigo-600 px-3 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500"
              :disabled="loading || !query"
              @click="runSearchAction"
            >
              <Search class="h-4 w-4" />
              Search
            </button>
            <button
              class="inline-flex h-10 items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 shadow-sm hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
              :disabled="loading"
              @click="resetSearch"
            >
              Reset
            </button>
            <button
              class="inline-flex h-10 items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 shadow-sm hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
              @click="copySearchLink"
            >
              Copy link
            </button>
          </div>
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-xs font-medium text-slate-600 whitespace-nowrap dark:text-slate-300"
            >Top K</label
          >
          <select
            v-model.number="topK"
            class="h-10 min-w-[84px] rounded-lg border border-slate-200 bg-white px-2 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          >
            <option :value="5">5</option>
            <option :value="10">10</option>
            <option :value="20">20</option>
          </select>
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-xs font-medium text-slate-600 whitespace-nowrap dark:text-slate-300"
            >Source</label
          >
          <select
            v-model="source"
            class="h-10 min-w-[160px] rounded-lg border border-slate-200 bg-white px-2 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          >
            <option value="">All</option>
            <option value="vision_ocr">Vision OCR</option>
            <option value="paperless_ocr">Paperless OCR</option>
            <option value="pdf_text">PDF text</option>
          </select>
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-xs font-medium text-slate-600 whitespace-nowrap dark:text-slate-300"
            >Min quality: {{ minQuality }}</label
          >
          <input
            type="range"
            min="0"
            max="100"
            v-model.number="minQuality"
            class="h-10 w-40"
          />
        </div>
        <div class="flex items-center gap-4 self-center">
          <label
            class="inline-flex items-center gap-2 text-xs font-medium text-slate-600 dark:text-slate-300"
          >
            <input type="checkbox" v-model="onlyVision" class="h-4 w-4" />
            Only vision OCR
          </label>
          <label
            class="inline-flex items-center gap-2 text-xs font-medium text-slate-600 dark:text-slate-300"
          >
            <input type="checkbox" v-model="dedupe" class="h-4 w-4" />
            Dedupe
          </label>
          <label
            class="inline-flex items-center gap-2 text-xs font-medium text-slate-600 dark:text-slate-300"
          >
            <input type="checkbox" v-model="rerank" class="h-4 w-4" />
            Rerank
          </label>
        </div>
      </div>

      <div
        v-if="error"
        class="mt-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-200"
      >
        {{ error }}
      </div>
      <div
        v-else-if="filteredResults.length === 0"
        class="mt-4 text-sm text-slate-500 dark:text-slate-400"
      >
        {{ hasSearched ? 'No matches found for the current query.' : 'No results yet.' }}
      </div>

      <div v-else class="mt-4 space-y-3">
        <div
          v-for="result in filteredResults"
          :key="`${result.doc_id}-${result.page}-${result.source}`"
          class="rounded-lg border border-slate-200 bg-slate-50 p-4 hover:border-indigo-200 dark:border-slate-800 dark:bg-slate-800 dark:hover:border-indigo-400/60"
        >
          <div class="text-xs text-slate-500 dark:text-slate-400">
            Doc {{ result.doc_id }} - Page {{ result.page ?? 'n/a' }} -
            {{ result.source || 'unknown' }} - Score
            {{ result.score?.toFixed ? result.score.toFixed(3) : result.score }} - Rerank
            {{ combinedScore(result) }}
            - Quality {{ result.quality_score }}
          </div>
          <div
            v-if="result.document"
            class="mt-1 text-sm font-medium text-slate-900 dark:text-slate-100"
          >
            {{ result.document.title || `Document ${result.doc_id}` }}
            <span class="text-xs text-slate-500 dark:text-slate-400">
              - {{ result.document.document_date || result.document.created || 'n/a' }}
            </span>
            <span
              v-if="result.document.correspondent_name"
              class="text-xs text-slate-500 dark:text-slate-400"
            >
              - {{ result.document.correspondent_name }}
            </span>
            <span v-if="paperlessBaseUrl" class="text-xs text-slate-500 dark:text-slate-400"></span>
          </div>
          <div class="mt-2 text-sm text-slate-700 dark:text-slate-200">{{ result.snippet }}</div>
          <div class="mt-3 flex items-center gap-2 text-xs">
            <a
              v-if="result.doc_id"
              class="rounded-md border border-slate-200 bg-white px-2 py-1 font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
              :href="resultLink(result)"
              target="_blank"
              rel="noopener noreferrer"
            >
              Open details
            </a>
            <a
              v-if="paperlessBaseUrl"
              class="rounded-md border border-indigo-200 bg-indigo-50 px-2 py-1 font-semibold text-indigo-700 hover:border-indigo-300 dark:border-indigo-900/50 dark:bg-indigo-950/40 dark:text-indigo-200"
              :href="`${paperlessBaseUrl.replace(/\/$/, '')}/documents/${result.doc_id}`"
              target="_blank"
              rel="noopener"
            >
              Open in Paperless
            </a>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { Search } from 'lucide-vue-next'
import { onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { usePaperlessBaseUrl } from '../composables/usePaperlessBaseUrl'
import { buildDocumentCitationLink } from '../services/citationJump'
import { useSearchSession, type SearchResult } from '../composables/useSearchSession'
import { useToastStore } from '../stores/toastStore'

const {
  query,
  topK,
  source,
  onlyVision,
  minQuality,
  dedupe,
  rerank,
  filteredResults,
  hasSearched,
  loading,
  error,
  runSearch,
} = useSearchSession()
const route = useRoute()
const router = useRouter()
const toastStore = useToastStore()
let syncingFromRoute = false
const { paperlessBaseUrl } = usePaperlessBaseUrl()

const combinedScore = (result: SearchResult) => {
  const value = (result as { combined_score?: number }).combined_score
  if (typeof value === 'number') return value.toFixed(3)
  if (value === null || value === undefined) return 'n/a'
  return String(value)
}

const resultLink = (result: SearchResult) => {
  return buildDocumentCitationLink({
    docId: result?.doc_id,
    page: result?.page,
    bbox: result?.bbox,
    source: result?.source,
    snippet: result?.snippet,
  })
}

const runSearchAction = async () => runSearch()

const parseBool = (value: unknown, fallback: boolean) => {
  const raw = Array.isArray(value) ? value[0] : value
  if (raw === '1' || raw === 'true') return true
  if (raw === '0' || raw === 'false') return false
  return fallback
}

const parseNumber = (value: unknown, fallback: number) => {
  const raw = Array.isArray(value) ? value[0] : value
  const parsed = Number(raw)
  return Number.isFinite(parsed) ? parsed : fallback
}

const buildQueryState = () => {
  const next: Record<string, string> = {}
  if (query.value.trim()) next.q = query.value.trim()
  if (topK.value !== 10) next.k = String(topK.value)
  if (source.value) next.src = source.value
  if (onlyVision.value) next.v = '1'
  if (minQuality.value > 0) next.minq = String(minQuality.value)
  if (!dedupe.value) next.dd = '0'
  if (!rerank.value) next.rr = '0'
  return next
}

const syncFromRoute = () => {
  syncingFromRoute = true
  const q = Array.isArray(route.query.q) ? route.query.q[0] : route.query.q
  query.value = typeof q === 'string' ? q : ''
  topK.value = parseNumber(route.query.k, 10)
  source.value = typeof route.query.src === 'string' ? route.query.src : ''
  onlyVision.value = parseBool(route.query.v, false)
  minQuality.value = parseNumber(route.query.minq, 0)
  dedupe.value = parseBool(route.query.dd, true)
  rerank.value = parseBool(route.query.rr, true)
  syncingFromRoute = false
}

const syncToRoute = async () => {
  const next = buildQueryState()
  const current = route.query
  const same =
    String(current.q || '') === String(next.q || '') &&
    String(current.k || '') === String(next.k || '') &&
    String(current.src || '') === String(next.src || '') &&
    String(current.v || '') === String(next.v || '') &&
    String(current.minq || '') === String(next.minq || '') &&
    String(current.dd || '') === String(next.dd || '') &&
    String(current.rr || '') === String(next.rr || '')
  if (same) return
  await router.replace({ query: next })
}

const resetSearch = async () => {
  query.value = ''
  topK.value = 10
  source.value = ''
  onlyVision.value = false
  minQuality.value = 0
  dedupe.value = true
  rerank.value = true
  await syncToRoute()
}

const copySearchLink = async () => {
  try {
    const href = `${window.location.origin}${router.resolve({ path: route.path, query: buildQueryState() }).href}`
    await navigator.clipboard.writeText(href)
    toastStore.push('Search link copied.', 'success', 'Search', 1600)
  } catch {
    toastStore.push('Failed to copy search link.', 'danger', 'Search', 2200)
  }
}

onMounted(async () => {
  syncFromRoute()
  if (query.value.trim()) {
    await runSearchAction()
  }
})

watch([query, topK, source, onlyVision, minQuality, dedupe, rerank], () => {
  if (syncingFromRoute) return
  void syncToRoute()
})

watch(
  () => route.query,
  () => {
    syncFromRoute()
  },
)
</script>
