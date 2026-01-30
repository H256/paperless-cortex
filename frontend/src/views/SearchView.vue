<template>
  <div>
    <h2 class="text-2xl font-semibold tracking-tight text-slate-900">Semantic Search</h2>
    <p class="mt-1 text-sm text-slate-500">Search across your documents with embeddings and citations.</p>

    <section class="mt-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <div class="flex flex-wrap items-end gap-4">
        <div class="flex-1 min-w-[260px]">
          <label class="text-xs font-medium text-slate-600">Query</label>
          <div class="mt-1 flex items-center gap-2">
            <input
              v-model="searchStore.query"
              class="h-10 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 text-sm text-slate-900 outline-none focus:border-indigo-400"
              type="text"
              placeholder="Ask a question or search..."
              @keyup.enter="runSearch"
            />
            <button
              class="inline-flex h-10 items-center gap-2 rounded-lg bg-indigo-600 px-3 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500"
              :disabled="searchStore.loading || !searchStore.query"
              @click="runSearch"
            >
              <Search class="h-4 w-4" />
              Search
            </button>
          </div>
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-xs font-medium text-slate-600 whitespace-nowrap">Top K</label>
          <select v-model.number="searchStore.topK" class="h-10 min-w-[84px] rounded-lg border border-slate-200 bg-white px-2 text-sm">
            <option :value="5">5</option>
            <option :value="10">10</option>
            <option :value="20">20</option>
          </select>
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-xs font-medium text-slate-600 whitespace-nowrap">Source</label>
          <select v-model="searchStore.source" class="h-10 min-w-[160px] rounded-lg border border-slate-200 bg-white px-2 text-sm">
            <option value="">All</option>
            <option value="vision_ocr">Vision OCR</option>
            <option value="paperless_ocr">Paperless OCR</option>
            <option value="pdf_text">PDF text</option>
          </select>
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-xs font-medium text-slate-600 whitespace-nowrap">Min quality: {{ searchStore.minQuality }}</label>
          <input type="range" min="0" max="100" v-model.number="searchStore.minQuality" class="h-10 w-40" />
        </div>
        <div class="flex items-center gap-4 self-center">
          <label class="inline-flex items-center gap-2 text-xs font-medium text-slate-600">
            <input type="checkbox" v-model="searchStore.onlyVision" class="h-4 w-4" />
            Only vision OCR
          </label>
          <label class="inline-flex items-center gap-2 text-xs font-medium text-slate-600">
            <input type="checkbox" v-model="searchStore.dedupe" class="h-4 w-4" />
            Dedupe
          </label>
          <label class="inline-flex items-center gap-2 text-xs font-medium text-slate-600">
            <input type="checkbox" v-model="searchStore.rerank" class="h-4 w-4" />
            Rerank
          </label>
        </div>
      </div>

      <div v-if="searchStore.error" class="mt-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
        {{ searchStore.error }}
      </div>
      <div v-else-if="filteredResults.length === 0" class="mt-4 text-sm text-slate-500">
        No results yet.
      </div>

      <div v-else class="mt-4 space-y-3">
        <div
          v-for="result in filteredResults"
          :key="`${result.doc_id}-${result.page}-${result.source}`"
          class="rounded-lg border border-slate-200 bg-slate-50 p-4 hover:border-indigo-200"
        >
          <div class="text-xs text-slate-500">
            Doc {{ result.doc_id }} · Page {{ result.page ?? 'n/a' }} · {{ result.source || 'unknown' }} ·
            Score {{ result.score?.toFixed ? result.score.toFixed(3) : result.score }} · Quality {{ result.quality_score }}
          </div>
          <div v-if="result.document" class="mt-1 text-sm font-medium text-slate-900">
            {{ result.document.title || `Document ${result.doc_id}` }}
            <span class="text-xs text-slate-500">
              · {{ result.document.document_date || result.document.created || 'n/a' }}
            </span>
            <span v-if="result.document.correspondent_name" class="text-xs text-slate-500">
              · {{ result.document.correspondent_name }}
            </span>
            <a
              v-if="paperlessBaseUrl"
              class="ml-2 text-xs font-semibold text-indigo-600 hover:text-indigo-500"
              :href="`${paperlessBaseUrl.replace(/\/$/, '')}/documents/${result.doc_id}`"
              target="_blank"
              rel="noopener"
            >
              Open in Paperless
            </a>
          </div>
          <div class="mt-2 text-sm text-slate-700">{{ result.snippet }}</div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { Search } from 'lucide-vue-next';
import { computed } from 'vue';
import { storeToRefs } from 'pinia';
import { useSearchStore } from '../stores/searchStore';
import { useStatusStore } from '../stores/statusStore';

const searchStore = useSearchStore();
const statusStore = useStatusStore();
const { filteredResults } = storeToRefs(searchStore);

const paperlessBaseUrl = computed(() => import.meta.env.VITE_PAPERLESS_BASE_URL || statusStore.paperlessBaseUrl || '');

const runSearch = async () => {
  await searchStore.runSearch();
};
</script>
