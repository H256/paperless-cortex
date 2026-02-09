<template>
  <section
    class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900"
  >
    <div class="flex items-center justify-between">
      <h3 class="text-lg font-semibold text-slate-900 dark:text-slate-100">
        Extracted page texts
      </h3>
      <span class="text-xs text-slate-500 dark:text-slate-400">
        {{ visionStatusText }}
      </span>
    </div>
    <div class="mt-4">
      <div class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
        Aggregated text context
      </div>
      <textarea
        class="mt-2 w-full min-h-[180px] rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
        readonly
        :value="aggregatedText"
      ></textarea>
    </div>
    <div v-if="pageTextsError" class="mt-3 text-sm text-rose-600 dark:text-rose-300">
      {{ pageTextsError }}
    </div>
    <div
      v-else-if="pageTexts.length === 0"
      class="mt-3 text-sm text-slate-500 dark:text-slate-400"
    >
      No extracted page text loaded.
    </div>
    <div v-else class="mt-4 space-y-4">
      <div
        class="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300"
      >
        <span>
          Showing {{ pageRangeStart }}-{{ pageRangeEnd }} of {{ pageTexts.length }} extracted entries
        </span>
        <div class="flex items-center gap-2">
          <label class="inline-flex items-center gap-1">
            <span>Per page</span>
            <select
              v-model.number="pageSize"
              class="rounded-md border border-slate-200 bg-white px-2 py-1 dark:border-slate-700 dark:bg-slate-900"
            >
              <option :value="10">10</option>
              <option :value="20">20</option>
              <option :value="50">50</option>
            </select>
          </label>
          <button
            class="rounded-md border border-slate-200 bg-white px-2 py-1 font-semibold disabled:opacity-50 dark:border-slate-700 dark:bg-slate-900"
            :disabled="pageIndex === 1"
            @click="pageIndex -= 1"
          >
            Prev
          </button>
          <span>{{ pageIndex }} / {{ totalPages }}</span>
          <button
            class="rounded-md border border-slate-200 bg-white px-2 py-1 font-semibold disabled:opacity-50 dark:border-slate-700 dark:bg-slate-900"
            :disabled="pageIndex >= totalPages"
            @click="pageIndex += 1"
          >
            Next
          </button>
        </div>
      </div>
      <div
        v-for="page in pagedPageTexts"
        :key="pageKey(page)"
        class="rounded-lg border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-800"
      >
        <div
          class="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500 dark:text-slate-400"
        >
          <span>Page {{ page.page }} - Source: {{ page.source }}</span>
          <button
            v-if="props.pdfPage !== page.page"
            class="rounded-md border border-slate-200 bg-white px-2 py-1 font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-slate-500"
            @click="emit('jumpToPage', page.page)"
          >
            Jump to PDF page
          </button>
          <button
            class="rounded-md border border-slate-200 bg-white px-2 py-1 font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-slate-500"
            @click="togglePage(page)"
          >
            {{ isExpanded(page) ? 'Hide' : 'Show' }}
          </button>
        </div>
        <div v-if="isExpanded(page)">
          <div v-if="page.quality" class="mt-2 text-xs text-slate-600 dark:text-slate-300">
            <div class="font-semibold text-slate-700 dark:text-slate-200">
              Quality score: {{ page.quality.score }}
            </div>
            <div v-if="page.quality.reasons?.length" class="mt-1">
              Reasons: {{ page.quality.reasons.join(', ') }}
            </div>
            <div class="mt-3 grid gap-2 md:grid-cols-3">
              <div
                v-for="(value, key) in page.quality.metrics"
                :key="key"
                class="rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
              >
                {{ key }}: {{ value.toFixed ? value.toFixed(3) : value }}
              </div>
            </div>
          </div>
          <div class="mt-3">
            <textarea
              class="w-full min-h-[140px] rounded-lg border border-slate-200 bg-white p-3 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
              readonly
              :value="page.text"
            ></textarea>
          </div>
        </div>
      </div>
    </div>

  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { PageText, VisionProgress } from '../services/documents'

const props = defineProps<{
  pageTexts: PageText[]
  visionProgress: VisionProgress | null
  pageTextsError: string
  aggregatedText: string
  pdfPage: number
}>()

const emit = defineEmits<{
  (e: 'jumpToPage', value: number): void
}>()

const expandedPages = ref<Set<string>>(new Set())
const pageIndex = ref(1)
const pageSize = ref(20)

const pageKey = (page: PageText) => `${page.page}:${page.source}`
const isExpanded = (page: PageText) => expandedPages.value.has(pageKey(page))
const togglePage = (page: PageText) => {
  const key = pageKey(page)
  if (expandedPages.value.has(key)) {
    expandedPages.value.delete(key)
  } else {
    expandedPages.value.add(key)
  }
}

const visionStatusText = computed(() => {
  const progress = props.visionProgress
  if (!progress) return 'Vision OCR progress unavailable'
  const done = progress.done_pages ?? 0
  const expected = progress.expected_pages
  const missing = progress.missing_pages
  const coverage = progress.coverage_percent
  if (!expected || expected <= 0) {
    return done > 0 ? `Vision OCR pages: ${done}` : 'Vision OCR not started'
  }
  const status = progress.is_complete ? 'complete' : 'incomplete'
  const missingLabel = typeof missing === 'number' ? `, missing ${missing}` : ''
  const coverageLabel = typeof coverage === 'number' ? ` (${coverage.toFixed(1)}%)` : ''
  return `Vision OCR ${status}: ${done}/${expected}${missingLabel}${coverageLabel}`
})

const totalPages = computed(() =>
  Math.max(1, Math.ceil(props.pageTexts.length / Math.max(1, pageSize.value))),
)

const safePageIndex = computed(() => Math.min(pageIndex.value, totalPages.value))

const pagedPageTexts = computed(() => {
  const start = (safePageIndex.value - 1) * pageSize.value
  return props.pageTexts.slice(start, start + pageSize.value)
})

const pageRangeStart = computed(() =>
  props.pageTexts.length === 0 ? 0 : (safePageIndex.value - 1) * pageSize.value + 1,
)

const pageRangeEnd = computed(() =>
  Math.min(props.pageTexts.length, safePageIndex.value * pageSize.value),
)

watch(
  [() => props.pageTexts.length, pageSize],
  () => {
    if (pageIndex.value > totalPages.value) {
      pageIndex.value = totalPages.value
    }
    if (pageIndex.value < 1) {
      pageIndex.value = 1
    }
  },
)
</script>
