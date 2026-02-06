<template>
  <section
    class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900"
  >
    <div class="flex items-center justify-between">
      <h3 class="text-lg font-semibold text-slate-900 dark:text-slate-100">
        Extracted page texts (debug)
      </h3>
      <span class="text-xs text-slate-500 dark:text-slate-400">Page-wise OCR</span>
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
        v-for="page in pageTexts"
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
          <div class="mt-3 grid gap-3 lg:grid-cols-[minmax(0,360px)_1fr]">
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
import { ref } from 'vue'
import type { PageText } from '../services/documents'

defineProps<{
  pageTexts: PageText[]
  pageTextsError: string
  aggregatedText: string
  pdfPage: number
}>()

const emit = defineEmits<{
  (e: 'jumpToPage', value: number): void
}>()

const expandedPages = ref<Set<string>>(new Set())

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
</script>
