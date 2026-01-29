<template>
  <section>
    <div class="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h2 class="text-2xl font-semibold tracking-tight text-slate-900">
          {{ document?.title || `Document ${id}` }}
        </h2>
        <p class="text-sm text-slate-500">Document ID: {{ id }}</p>
      </div>
      <div class="flex items-center gap-2">
        <a
          v-if="paperlessUrl"
          :href="paperlessUrl"
          target="_blank"
          rel="noopener"
          class="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 shadow-sm hover:border-slate-300"
        >
          <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 3h7v7" />
            <path d="M10 14L21 3" />
            <path d="M5 7v14h14v-7" />
          </svg>
          Paperless
        </a>
        <button
          class="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-slate-800"
          @click="load"
        >
          <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 12a9 9 0 1 1-3.3-6.9" />
            <polyline points="21 3 21 9 15 9" />
          </svg>
          Reload
        </button>
      </div>
    </div>

    <section class="mt-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div class="flex flex-wrap items-center gap-3">
        <div class="flex flex-wrap items-center gap-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-600">
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
          <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M4 4v6h6" />
            <path d="M20 20v-6h-6" />
            <path d="M4 10a8 8 0 0 1 14.9-3" />
            <path d="M20 14a8 8 0 0 1-14.9 3" />
          </svg>
          {{ processing ? 'Processing...' : 'Re-process' }}
        </button>
      </div>
    </section>

    <div v-if="loading" class="mt-6 text-sm text-slate-500">Loading...</div>
    <div v-else class="mt-6 space-y-6">
      <section class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div class="text-xs font-semibold uppercase tracking-wide text-slate-400">Metadata</div>
        <dl class="mt-4 grid gap-4 md:grid-cols-2">
          <div v-for="row in rows" :key="row.label" class="rounded-lg border border-slate-200 bg-slate-50 p-3">
            <dt class="text-xs font-semibold uppercase tracking-wide text-slate-400">{{ row.label }}</dt>
            <dd class="mt-1 text-sm text-slate-900 break-words">{{ row.value }}</dd>
          </div>
        </dl>
      </section>

      <section class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div class="flex items-center justify-between">
          <h3 class="text-lg font-semibold text-slate-900">Text layer</h3>
          <span class="text-xs font-semibold text-slate-500">Baseline OCR</span>
        </div>
        <textarea
          class="mt-4 w-full min-h-[260px] rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-900"
          readonly
          :value="document?.content || ''"
        ></textarea>

        <div class="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4">
          <div class="text-sm font-semibold text-slate-700">Text quality (baseline)</div>
          <div v-if="contentQualityError" class="mt-2 text-sm text-rose-600">
            {{ contentQualityError }}
          </div>
          <div v-else-if="!contentQuality" class="mt-2 text-sm text-slate-500">
            No quality metrics loaded.
          </div>
          <div v-else class="mt-3 text-xs text-slate-600">
            <div class="font-semibold text-slate-700">Quality score: {{ contentQuality.score }}</div>
            <div v-if="contentQuality.reasons?.length" class="mt-1">
              Reasons: {{ contentQuality.reasons.join(', ') }}
            </div>
            <div class="mt-3 grid gap-2 md:grid-cols-3">
              <div
                v-for="(value, key) in contentQuality.metrics"
                :key="key"
                class="rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] text-slate-600"
              >
                {{ key }}: {{ value.toFixed ? value.toFixed(3) : value }}
              </div>
            </div>
          </div>
        </div>
      </section>

      <section class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div class="flex items-center justify-between">
          <h3 class="text-lg font-semibold text-slate-900">AI suggestions</h3>
          <span class="text-xs text-slate-500">Paperless OCR ? Vision OCR ? Best pick</span>
        </div>
        <div v-if="suggestionsError" class="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {{ suggestionsError }}
        </div>
        <div v-else-if="!suggestions" class="mt-3 text-sm text-slate-500">
          No suggestions loaded.
        </div>
        <div v-else class="mt-4 space-y-4">
          <div class="rounded-xl border border-slate-200 bg-slate-50 p-4">
            <div class="flex items-center justify-between">
              <strong class="text-sm text-slate-900">Best pick</strong>
            </div>
            <div v-if="!bestPickSuggestion" class="mt-3 text-sm text-slate-500"><em>No data.</em></div>
            <div v-else class="mt-3 space-y-3">
              <div v-if="bestPickSuggestion.raw">
                <div class="text-xs font-semibold text-slate-500">Raw output</div>
                <pre class="mt-1 max-h-40 overflow-auto rounded-md border border-slate-200 bg-white p-2 text-xs text-slate-600">{{ bestPickSuggestion.raw }}</pre>
              </div>
              <div v-if="bestPickSuggestion.data" class="space-y-2">
                <div class="flex items-center justify-between text-xs text-slate-500">
                  <span>Summary</span>
                  <button
                    class="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-700 hover:border-emerald-300"
                    @click="applyToDocument('best_pick', 'note', bestPickSuggestion.data)"
                  >
                    Save note
                  </button>
                </div>
                <div class="text-sm text-slate-900">{{ bestPickSuggestion.data.summary }}</div>
                <div class="grid gap-2">
                  <div class="flex items-center justify-between text-xs text-slate-500">
                    <span>Document type</span>
                    <span class="text-slate-900">{{ bestPickSuggestion.data.documentType }}</span>
                  </div>
                  <div class="flex items-center justify-between text-xs text-slate-500">
                    <span>Language</span>
                    <span class="text-slate-900">{{ bestPickSuggestion.data.language }}</span>
                  </div>
                </div>
                <div v-for="field in suggestionFields" :key="`best-${field.key}`" class="grid grid-cols-1 gap-2 border-t border-slate-200 pt-2 md:grid-cols-[140px_1fr_auto]">
                  <span class="text-xs text-slate-500">{{ field.label }}</span>
                  <div class="text-sm text-slate-900">{{ fieldValue(bestPickSuggestion.data, field.key) }}</div>
                  <button
                    class="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-700 hover:border-emerald-300"
                    @click="applyToDocument('best_pick', field.key, bestPickSuggestion.data)"
                  >
                    Save
                  </button>
                </div>
                <div
                  v-if="(bestPickSuggestion.data.suggested_tags_existing || []).length || (bestPickSuggestion.data.suggested_tags_new || []).length"
                  class="rounded-md border border-slate-200 bg-white p-2 text-xs text-slate-600"
                >
                  <div>Existing tags: {{ (bestPickSuggestion.data.suggested_tags_existing || []).join(', ') }}</div>
                  <div>New tags: {{ (bestPickSuggestion.data.suggested_tags_new || []).join(', ') }}</div>
                </div>
              </div>
            </div>
          </div>

          <div class="grid gap-4 lg:grid-cols-2">
            <div class="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <div class="flex items-center justify-between">
                <strong class="text-sm text-slate-900">Paperless OCR</strong>
                <button
                  class="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-semibold text-slate-600 hover:border-slate-300"
                  :disabled="suggestionsLoading"
                  @click="refreshSuggestions('paperless_ocr')"
                >
                  Refresh
                </button>
              </div>
              <div v-if="!paperlessSuggestion" class="mt-3 text-sm text-slate-500"><em>No data.</em></div>
              <div v-else class="mt-3 space-y-3">
                <div v-if="paperlessSuggestion.raw">
                  <div class="text-xs font-semibold text-slate-500">Raw output</div>
                  <pre class="mt-1 max-h-40 overflow-auto rounded-md border border-slate-200 bg-white p-2 text-xs text-slate-600">{{ paperlessSuggestion.raw }}</pre>
                </div>
                <div v-if="paperlessSuggestion.data" class="space-y-2">
                  <div class="text-xs text-slate-500">Summary</div>
                  <div class="text-sm text-slate-900">{{ paperlessSuggestion.data.summary }}</div>
                  <div class="grid gap-2">
                    <div class="flex items-center justify-between text-xs text-slate-500">
                      <span>Document type</span>
                      <span class="text-slate-900">{{ paperlessSuggestion.data.documentType || paperlessSuggestion.data.suggested_document_type }}</span>
                    </div>
                    <div class="flex items-center justify-between text-xs text-slate-500">
                      <span>Language</span>
                      <span class="text-slate-900">{{ paperlessSuggestion.data.language }}</span>
                    </div>
                  </div>
                  <div v-for="field in suggestionFields" :key="`paperless-${field.key}`" class="grid grid-cols-1 gap-2 border-t border-slate-200 pt-2 md:grid-cols-[140px_1fr_auto]">
                    <span class="text-xs text-slate-500">{{ field.label }}</span>
                    <div class="text-sm text-slate-900">{{ fieldValue(paperlessSuggestion.data, field.key) }}</div>
                    <div class="flex items-center gap-2">
                      <button
                        class="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-semibold text-slate-600 hover:border-slate-300"
                        :disabled="suggestionVariantLoading[`paperless_ocr:${field.key}`]"
                        @click="suggestField('paperless_ocr', field.key)"
                      >
                        Suggest new
                      </button>
                      <button
                        class="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-700 hover:border-emerald-300"
                        @click="applyToDocument('paperless_ocr', field.key, paperlessSuggestion.data)"
                      >
                        Save
                      </button>
                    </div>
                  </div>
                  <div
                    v-if="(paperlessSuggestion.data.suggested_tags_existing || []).length || (paperlessSuggestion.data.suggested_tags_new || []).length"
                    class="rounded-md border border-slate-200 bg-white p-2 text-xs text-slate-600"
                  >
                    <div>Existing tags: {{ (paperlessSuggestion.data.suggested_tags_existing || []).join(', ') }}</div>
                    <div>New tags: {{ (paperlessSuggestion.data.suggested_tags_new || []).join(', ') }}</div>
                  </div>
                  <div
                    v-for="field in suggestionFields"
                    :key="`paperless-variants-${field.key}`"
                    class="rounded-md border border-dashed border-slate-200 bg-white p-2"
                  >
                    <div v-if="suggestionVariantError[`paperless_ocr:${field.key}`]" class="text-xs text-rose-600">
                      {{ suggestionVariantError[`paperless_ocr:${field.key}`] }}
                    </div>
                    <div v-if="(suggestionVariants[`paperless_ocr:${field.key}`] || []).length">
                      <div class="text-xs font-semibold text-slate-500">Variants for {{ field.label }}</div>
                      <div v-for="variant in suggestionVariants[`paperless_ocr:${field.key}`]" :key="`${field.key}-${variant}`" class="mt-1 flex items-center justify-between gap-2 text-xs">
                        <span class="text-slate-700">{{ Array.isArray(variant) ? variant.join(', ') : variant }}</span>
                        <button
                          class="rounded-md border border-slate-200 bg-slate-50 px-2 py-1 font-semibold text-slate-600 hover:border-slate-300"
                          @click="applyVariant('paperless_ocr', field.key, variant)"
                        >
                          Use
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div class="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <div class="flex items-center justify-between">
                <strong class="text-sm text-slate-900">Vision OCR</strong>
                <button
                  class="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-semibold text-slate-600 hover:border-slate-300"
                  :disabled="suggestionsLoading"
                  @click="refreshSuggestions('vision_ocr')"
                >
                  Refresh
                </button>
              </div>
              <div v-if="!visionSuggestion" class="mt-3 text-sm text-slate-500"><em>No data.</em></div>
              <div v-else class="mt-3 space-y-3">
                <div v-if="visionSuggestion.raw">
                  <div class="text-xs font-semibold text-slate-500">Raw output</div>
                  <pre class="mt-1 max-h-40 overflow-auto rounded-md border border-slate-200 bg-white p-2 text-xs text-slate-600">{{ visionSuggestion.raw }}</pre>
                </div>
                <div v-if="visionSuggestion.data" class="space-y-2">
                  <div class="text-xs text-slate-500">Summary</div>
                  <div class="text-sm text-slate-900">{{ visionSuggestion.data.summary }}</div>
                  <div class="grid gap-2">
                    <div class="flex items-center justify-between text-xs text-slate-500">
                      <span>Document type</span>
                      <span class="text-slate-900">{{ visionSuggestion.data.documentType || visionSuggestion.data.suggested_document_type }}</span>
                    </div>
                    <div class="flex items-center justify-between text-xs text-slate-500">
                      <span>Language</span>
                      <span class="text-slate-900">{{ visionSuggestion.data.language }}</span>
                    </div>
                  </div>
                  <div v-for="field in suggestionFields" :key="`vision-${field.key}`" class="grid grid-cols-1 gap-2 border-t border-slate-200 pt-2 md:grid-cols-[140px_1fr_auto]">
                    <span class="text-xs text-slate-500">{{ field.label }}</span>
                    <div class="text-sm text-slate-900">{{ fieldValue(visionSuggestion.data, field.key) }}</div>
                    <div class="flex items-center gap-2">
                      <button
                        class="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-semibold text-slate-600 hover:border-slate-300"
                        :disabled="suggestionVariantLoading[`vision_ocr:${field.key}`]"
                        @click="suggestField('vision_ocr', field.key)"
                      >
                        Suggest new
                      </button>
                      <button
                        class="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-700 hover:border-emerald-300"
                        @click="applyToDocument('vision_ocr', field.key, visionSuggestion.data)"
                      >
                        Save
                      </button>
                    </div>
                  </div>
                  <div
                    v-if="(visionSuggestion.data.suggested_tags_existing || []).length || (visionSuggestion.data.suggested_tags_new || []).length"
                    class="rounded-md border border-slate-200 bg-white p-2 text-xs text-slate-600"
                  >
                    <div>Existing tags: {{ (visionSuggestion.data.suggested_tags_existing || []).join(', ') }}</div>
                    <div>New tags: {{ (visionSuggestion.data.suggested_tags_new || []).join(', ') }}</div>
                  </div>
                  <div
                    v-for="field in suggestionFields"
                    :key="`vision-variants-${field.key}`"
                    class="rounded-md border border-dashed border-slate-200 bg-white p-2"
                  >
                    <div v-if="suggestionVariantError[`vision_ocr:${field.key}`]" class="text-xs text-rose-600">
                      {{ suggestionVariantError[`vision_ocr:${field.key}`] }}
                    </div>
                    <div v-if="(suggestionVariants[`vision_ocr:${field.key}`] || []).length">
                      <div class="text-xs font-semibold text-slate-500">Variants for {{ field.label }}</div>
                      <div v-for="variant in suggestionVariants[`vision_ocr:${field.key}`]" :key="`${field.key}-${variant}`" class="mt-1 flex items-center justify-between gap-2 text-xs">
                        <span class="text-slate-700">{{ Array.isArray(variant) ? variant.join(', ') : variant }}</span>
                        <button
                          class="rounded-md border border-slate-200 bg-slate-50 px-2 py-1 font-semibold text-slate-600 hover:border-slate-300"
                          @click="applyVariant('vision_ocr', field.key, variant)"
                        >
                          Use
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div class="flex items-center justify-between">
          <h3 class="text-lg font-semibold text-slate-900">Extracted page texts (debug)</h3>
          <span class="text-xs text-slate-500">Page-wise OCR</span>
        </div>
        <div class="mt-4">
          <div class="text-xs font-semibold uppercase tracking-wide text-slate-400">Aggregated text context</div>
          <textarea
            class="mt-2 w-full min-h-[180px] rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-900"
            readonly
            :value="aggregatedText"
          ></textarea>
        </div>
        <div v-if="pageTextsError" class="mt-3 text-sm text-rose-600">{{ pageTextsError }}</div>
        <div v-else-if="pageTexts.length === 0" class="mt-3 text-sm text-slate-500">
          No extracted page text loaded.
        </div>
        <div v-else class="mt-4 space-y-4">
          <div v-for="page in pageTexts" :key="page.page" class="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <div class="text-xs text-slate-500">Page {{ page.page }} ? Source: {{ page.source }}</div>
            <div v-if="page.quality" class="mt-2 text-xs text-slate-600">
              <div class="font-semibold text-slate-700">Quality score: {{ page.quality.score }}</div>
              <div v-if="page.quality.reasons?.length" class="mt-1">Reasons: {{ page.quality.reasons.join(', ') }}</div>
              <div class="mt-3 grid gap-2 md:grid-cols-3">
                <div
                  v-for="(value, key) in page.quality.metrics"
                  :key="key"
                  class="rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] text-slate-600"
                >
                  {{ key }}: {{ value.toFixed ? value.toFixed(3) : value }}
                </div>
              </div>
            </div>
            <textarea
              class="mt-3 w-full min-h-[140px] rounded-lg border border-slate-200 bg-white p-3 text-sm text-slate-900"
              readonly
              :value="page.text"
            ></textarea>
          </div>
        </div>
      </section>
    </div>
  </section>
</template>


<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';
import { api, Page } from '../api';

interface DocumentDetail {
  id: number;
  title: string;
  document_date?: string | null;
  created?: string | null;
  modified?: string | null;
  correspondent?: number | null;
  correspondent_name?: string | null;
  document_type?: number | null;
  document_type_name?: string | null;
  tags?: number[];
  notes?: { note: string }[];
  content?: string;
  original_file_name?: string | null;
}

interface Tag {
  id: number;
  name: string;
}

interface Correspondent {
  id: number;
  name: string;
}

interface DocumentType {
  id: number;
  name: string;
}

interface PageText {
  page: number;
  source: string;
  text: string;
  quality?: {
    score: number;
    reasons: string[];
    metrics: Record<string, number>;
  };
}

const route = useRoute();
const id = Number(route.params.id);
const document = ref<DocumentDetail | null>(null);
const loading = ref(false);
const syncing = ref(false);
const processing = ref(false);
const doResync = ref(true);
const doReembed = ref(true);
const doQuality = ref(true);
const doPages = ref(false);
const doSuggestions = ref(false);
const paperlessBaseUrl = import.meta.env.VITE_PAPERLESS_BASE_URL || '';
const paperlessUrl = computed(() =>
  paperlessBaseUrl && document.value
    ? `${paperlessBaseUrl.replace(/\/$/, '')}/documents/${document.value.id}`
    : ''
);
const tags = ref<Tag[]>([]);
const correspondents = ref<Correspondent[]>([]);
const docTypes = ref<DocumentType[]>([]);
const pageTexts = ref<PageText[]>([]);
const pageTextsLoading = ref(false);
const pageTextsError = ref('');
const contentQuality = ref<{ score: number; reasons: string[]; metrics: Record<string, number> } | null>(null);
const contentQualityLoading = ref(false);
const contentQualityError = ref('');
const suggestions = ref<{ paperless_ocr?: any; vision_ocr?: any; best_pick?: any } | null>(null);
const suggestionsLoading = ref(false);
const suggestionsError = ref('');

const normalizeSuggestion = (input: any) => {
  if (!input || (typeof input === 'object' && Object.keys(input).length === 0)) {
    return null;
  }
  const raw = input.raw || null;
  const data = input.parsed || (raw ? null : input);
  return { raw, data };
};

const paperlessSuggestion = computed(() => normalizeSuggestion(suggestions.value?.paperless_ocr));
const visionSuggestion = computed(() => normalizeSuggestion(suggestions.value?.vision_ocr));
const bestPickSuggestion = computed(() => normalizeSuggestion(suggestions.value?.best_pick));
const suggestionFields = [
  { key: 'title', label: 'Suggested title' },
  { key: 'date', label: 'Suggested date' },
  { key: 'correspondent', label: 'Suggested correspondent' },
  { key: 'tags', label: 'Suggested tags' },
];
const suggestionVariants = ref<Record<string, any[]>>({});
const suggestionVariantLoading = ref<Record<string, boolean>>({});
const suggestionVariantError = ref<Record<string, string>>({});

const aggregatedText = computed(() => {
  if (!pageTexts.value.length) return document.value?.content || '';
  return pageTexts.value.map((page) => page.text).join('\n\n');
});

const fieldValue = (data: any, field: string) => {
  if (!data) return '';
  if (field === 'title') return data.title || data.suggested_title || '';
  if (field === 'date') {
    const raw = data.date || data.suggested_document_date || '';
    return formatDate(raw);
  }
  if (field === 'correspondent') return data.correspondent || data.suggested_correspondent || '';
  if (field === 'tags') return (data.tags || data.suggested_tags || []).join(', ');
  return data[field] ?? '';
};

const suggestField = async (source: 'paperless_ocr' | 'vision_ocr', field: string) => {
  const key = `${source}:${field}`;
  suggestionVariantLoading.value[key] = true;
  suggestionVariantError.value[key] = '';
  try {
    const { data } = await api.post<{ variants: any }>(`/documents/${id}/suggestions/field`, {
      source,
      field,
      count: 3,
    });
    const variants = data.variants?.parsed?.variants || data.variants?.variants || [];
    suggestionVariants.value[key] = Array.isArray(variants) ? variants : [];
  } catch (err: any) {
    suggestionVariantError.value[key] = err?.message ?? 'Failed to generate variants';
  } finally {
    suggestionVariantLoading.value[key] = false;
  }
};

const applyVariant = async (
  source: 'paperless_ocr' | 'vision_ocr',
  field: string,
  value: any
) => {
  const label = typeof value === 'string' ? value : JSON.stringify(value);
  const ok = window.confirm(`Overwrite ${field} with: ${label}?`);
  if (!ok) return;
  suggestionsLoading.value = true;
  suggestionsError.value = '';
  try {
    const { data } = await api.post<{ suggestions: { paperless_ocr?: any; vision_ocr?: any } }>(
      `/documents/${id}/suggestions/field/apply`,
      { source, field, value }
    );
    if (data?.suggestions) {
      suggestions.value = { ...(suggestions.value ?? {}), ...data.suggestions };
    }
  } catch (err: any) {
    suggestionsError.value = err?.message ?? 'Failed to apply suggestion';
  } finally {
    suggestionsLoading.value = false;
  }
};

const applyToDocument = async (source: string, field: string, data: any) => {
  if (!data) return;
  let value: any = data[field];
  if (field === 'title') value = data.title || data.suggested_title || '';
  if (field === 'date') value = data.date || data.suggested_document_date || '';
  if (field === 'correspondent') value = data.correspondent || data.suggested_correspondent || '';
  if (field === 'tags') value = data.tags || data.suggested_tags || [];
  if (value === null || value === undefined || value === '') return;
  const label = typeof value === 'string' ? value : JSON.stringify(value);
  const ok = window.confirm(`Apply ${field} to document: ${label}?`);
  if (!ok) return;
  try {
    await api.post(`/documents/${id}/apply-suggestion`, { source, field, value });
    await load();
  } catch (err: any) {
    suggestionsError.value = err?.message ?? 'Failed to apply suggestion to document';
  }
};


const rows = computed(() => {
  if (!document.value) return [];
  const notes = (document.value.notes || []).map((n) => n.note).join(' ');
  const tagNames = (document.value.tags || [])
    .map((tagId) => tags.value.find((t) => t.id === tagId)?.name ?? tagId)
    .join(', ');
  const correspondentName =
    document.value.correspondent_name ??
    correspondents.value.find((c) => c.id === document.value?.correspondent)?.name ??
    document.value.correspondent;
  const docTypeName =
    document.value.document_type_name ??
    docTypes.value.find((d) => d.id === document.value?.document_type)?.name ??
    document.value.document_type;
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
  ];
});

const formatDate = (value?: string | null) => {
  if (!value) return '';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat(navigator.language).format(parsed);
};

const formatDateTime = (value?: string | null) => {
  if (!value) return '';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat(navigator.language, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(parsed);
};

const load = async () => {
  loading.value = true;
  const { data } = await api.get<DocumentDetail>(`/documents/${id}/local`);
  if (data?.status === 'missing') {
    document.value = null;
  } else {
    document.value = data;
  }
  loading.value = false;
};

const resync = async () => {
  syncing.value = true;
  try {
    await api.post(`/sync/documents/${id}`, undefined, {
      params: { embed: doReembed.value, force_embed: doReembed.value },
    });
    await load();
  } finally {
    syncing.value = false;
  }
};

const loadMeta = async () => {
  const [tagsResp, corrResp] = await Promise.all([
    api.get<Page<Tag>>('/tags', { params: { page: 1, page_size: 200 } }),
    api.get<Page<Correspondent>>('/correspondents', { params: { page: 1, page_size: 200 } }),
  ]);
  tags.value = tagsResp.data.results ?? [];
  correspondents.value = corrResp.data.results ?? [];
  if (document.value?.document_type) {
    const { data } = await api.get<DocumentType>(`/document-types/${document.value.document_type}`);
    docTypes.value = [data];
  }
};

const loadPageTexts = async () => {
  pageTextsLoading.value = true;
  pageTextsError.value = '';
  try {
    const { data } = await api.get<{ pages: PageText[] }>(`/documents/${id}/page-texts`);
    pageTexts.value = data.pages ?? [];
  } catch (err: any) {
    pageTextsError.value = err?.message ?? 'Failed to load page texts';
  } finally {
    pageTextsLoading.value = false;
  }
};

const loadContentQuality = async () => {
  contentQualityLoading.value = true;
  contentQualityError.value = '';
  try {
    const { data } = await api.get<{ quality: { score: number; reasons: string[]; metrics: Record<string, number> } }>(
      `/documents/${id}/text-quality`
    );
    contentQuality.value = data.quality ?? null;
  } catch (err: any) {
    contentQualityError.value = err?.message ?? 'Failed to load text quality';
  } finally {
    contentQualityLoading.value = false;
  }
};

const loadSuggestions = async () => {
  suggestionsLoading.value = true;
  suggestionsError.value = '';
  try {
    const { data } = await api.get<{ suggestions: { paperless_ocr?: any; vision_ocr?: any } }>(`/documents/${id}/suggestions`);
    suggestions.value = data.suggestions ?? null;
  } catch (err: any) {
    suggestionsError.value = err?.message ?? 'Failed to load suggestions';
  } finally {
    suggestionsLoading.value = false;
  }
};

const refreshSuggestions = async (source: 'paperless_ocr' | 'vision_ocr') => {
  suggestionsLoading.value = true;
  suggestionsError.value = '';
  try {
    const { data } = await api.get<{ suggestions: { paperless_ocr?: any; vision_ocr?: any } }>(
      `/documents/${id}/suggestions`,
      { params: { source, refresh: true } }
    );
    suggestions.value = {
      ...(suggestions.value ?? {}),
      ...(data.suggestions ?? {}),
    };
  } catch (err: any) {
    suggestionsError.value = err?.message ?? 'Failed to refresh suggestions';
  } finally {
    suggestionsLoading.value = false;
  }
};

const runReprocess = async () => {
  processing.value = true;
  try {
    if (doResync.value) {
      await resync();
    }
    if (doQuality.value) {
      await loadContentQuality();
    }
    if (doPages.value) {
      await loadPageTexts();
    }
    if (doSuggestions.value) {
      await loadSuggestions();
    }
  } finally {
    processing.value = false;
  }
};

onMounted(async () => {
  await load();
  await loadMeta();
  await loadContentQuality();
  await loadPageTexts();
  await loadSuggestions();
});
</script>
