<template>
  <div>
    <h2 class="text-2xl font-semibold tracking-tight text-slate-900">Semantic Search</h2>
    <p class="mt-1 text-sm text-slate-500">Search across your documents with embeddings and citations.</p>

    <section class="mt-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <div class="flex flex-wrap items-center gap-3">
        <div class="flex-1 min-w-[240px]">
          <label class="text-xs font-medium text-slate-600">Query</label>
          <div class="mt-1 flex items-center gap-2">
            <input
              v-model="searchQuery"
              class="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 outline-none focus:border-indigo-400"
              type="text"
              placeholder="Ask a question or search..."
              @keyup.enter="runSearch"
            />
            <button
              class="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500"
              :disabled="searchLoading || !searchQuery"
              @click="runSearch"
            >
              <Search class="h-4 w-4" />
              Search
            </button>
          </div>
        </div>
        <div>
          <label class="text-xs font-medium text-slate-600">Top K</label>
          <select v-model.number="searchTopK" class="mt-1 rounded-lg border border-slate-200 bg-white px-2 py-2 text-sm">
            <option :value="5">5</option>
            <option :value="10">10</option>
            <option :value="20">20</option>
          </select>
        </div>
        <div>
          <label class="text-xs font-medium text-slate-600">Source</label>
          <select v-model="searchSource" class="mt-1 rounded-lg border border-slate-200 bg-white px-2 py-2 text-sm">
            <option value="">All</option>
            <option value="vision_ocr">Vision OCR</option>
            <option value="paperless_ocr">Paperless OCR</option>
            <option value="pdf_text">PDF text</option>
          </select>
        </div>
        <div class="flex items-center gap-2">
          <label class="inline-flex items-center gap-2 text-xs font-medium text-slate-600">
            <input type="checkbox" v-model="searchOnlyVision" />
            Only vision OCR
          </label>
        </div>
        <div>
          <label class="text-xs font-medium text-slate-600">Min quality: {{ searchMinQuality }}</label>
          <input type="range" min="0" max="100" v-model.number="searchMinQuality" class="mt-1 w-32" />
        </div>
        <div class="flex items-center gap-2">
          <label class="inline-flex items-center gap-2 text-xs font-medium text-slate-600">
            <input type="checkbox" v-model="searchDedupe" />
            Dedupe
          </label>
          <label class="inline-flex items-center gap-2 text-xs font-medium text-slate-600">
            <input type="checkbox" v-model="searchRerank" />
            Rerank
          </label>
        </div>
      </div>

      <div v-if="searchError" class="mt-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
        {{ searchError }}
      </div>
      <div v-else-if="searchResults.length === 0" class="mt-4 text-sm text-slate-500">
        No results yet.
      </div>

      <div v-else class="mt-4 space-y-3">
        <div
          v-for="result in filteredSearchResults"
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
import { computed, ref } from 'vue';
import { api } from '../api';

interface SearchResult {
  doc_id: number;
  page?: number | null;
  snippet: string;
  score?: number | null;
  source?: string | null;
  quality_score?: number | null;
  document?: {
    id: number;
    title?: string | null;
    document_date?: string | null;
    created?: string | null;
    correspondent_id?: number | null;
    correspondent_name?: string | null;
  } | null;
}

const searchQuery = ref('');
const searchTopK = ref(10);
const searchSource = ref('');
const searchOnlyVision = ref(false);
const searchMinQuality = ref(0);
const searchResults = ref<SearchResult[]>([]);
const searchLoading = ref(false);
const searchError = ref('');
const searchDedupe = ref(true);
const searchRerank = ref(true);
const paperlessBaseUrl = import.meta.env.VITE_PAPERLESS_BASE_URL || '';

const effectiveSource = computed(() => {
  if (searchOnlyVision.value) return 'vision_ocr';
  return searchSource.value || '';
});

const filteredSearchResults = computed(() => {
  if (!effectiveSource.value) return searchResults.value;
  return searchResults.value.filter((result) => result.source === effectiveSource.value);
});

const runSearch = async () => {
  if (!searchQuery.value) return;
  searchLoading.value = true;
  searchError.value = '';
  try {
    const { data } = await api.get<{ matches: SearchResult[] }>('/embeddings/search', {
      params: {
        q: searchQuery.value,
        top_k: searchTopK.value,
        source: effectiveSource.value || undefined,
        dedupe: searchDedupe.value,
        rerank: searchRerank.value,
        min_quality: searchMinQuality.value || undefined,
      },
    });
    searchResults.value = data.matches ?? [];
  } catch (err: any) {
    searchError.value = err?.message ?? 'Search failed';
  } finally {
    searchLoading.value = false;
  }
};
</script>
