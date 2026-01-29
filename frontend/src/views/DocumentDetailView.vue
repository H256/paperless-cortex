<template>
  <section class="detail">
    <div class="detail__header">
      <h2>{{ document?.title || `Document ${id}` }}</h2>
      <div class="detail__actions">
        <a v-if="paperlessUrl" :href="paperlessUrl" target="_blank" rel="noopener">
          <button type="button">View in Paperless</button>
        </a>
        <button @click="load">Reload</button>
      </div>
    </div>
    <div class="detail__reprocess">
      <div class="detail__reprocess__controls">
        <label>
          <input type="checkbox" v-model="doResync" />
          Resync
        </label>
        <label>
          <input type="checkbox" v-model="doReembed" :disabled="!doResync" />
          Re-embed
        </label>
        <label>
          <input type="checkbox" v-model="doQuality" />
          Analyze quality
        </label>
        <label>
          <input type="checkbox" v-model="doPages" />
          Load extracted pages
        </label>
        <label>
          <input type="checkbox" v-model="doSuggestions" />
          Generate suggestions
        </label>
      </div>
      <button :disabled="processing" @click="runReprocess">
        {{ processing ? 'Processing...' : 'Re-process' }}
      </button>
    </div>

    <div v-if="loading">Loading...</div>
    <div v-else>
      <table class="detail__table">
        <tbody>
          <tr v-for="row in rows" :key="row.label">
            <th>{{ row.label }}</th>
            <td>{{ row.value }}</td>
          </tr>
        </tbody>
      </table>

      <h3>Text layer</h3>
      <textarea class="detail__text" readonly :value="document?.content || ''"></textarea>
      <div class="detail__text-quality">
        <div class="detail__text-quality__header">
          <strong>Text quality (baseline)</strong>
        </div>
        <div v-if="contentQualityError" class="detail__text-quality__error">
          {{ contentQualityError }}
        </div>
        <div v-else-if="!contentQuality">
          <em>No quality metrics loaded.</em>
        </div>
        <div v-else class="detail__text-quality__body">
          <div class="detail__text-quality__score">Quality score: {{ contentQuality.score }}</div>
          <div v-if="contentQuality.reasons?.length" class="detail__text-quality__reasons">
            Reasons: {{ contentQuality.reasons.join(', ') }}
          </div>
          <div class="detail__text-quality__metrics">
            <div
              v-for="(value, key) in contentQuality.metrics"
              :key="key"
              class="detail__text-quality__metric"
            >
              {{ key }}: {{ value.toFixed ? value.toFixed(3) : value }}
            </div>
          </div>
        </div>
      </div>

      <div class="detail__suggestions">
        <div class="detail__suggestions__header">
          <strong>AI suggestions</strong>
        </div>
        <div v-if="suggestionsError" class="detail__suggestions__error">
          {{ suggestionsError }}
        </div>
        <div v-else-if="!suggestions">
          <em>No suggestions loaded.</em>
        </div>
        <div v-else class="detail__suggestions__body detail__suggestions__grid">
          <div class="detail__suggestions__column">
            <div class="detail__suggestions__column-header">
              <strong>Paperless OCR</strong>
              <button :disabled="suggestionsLoading" @click="refreshSuggestions('paperless_ocr')">
                Refresh
              </button>
            </div>
            <div v-if="!paperlessSuggestion"><em>No data.</em></div>
            <div v-else>
              <div v-if="paperlessSuggestion.raw">
                <strong>Raw output</strong>
                <pre class="detail__suggestions__raw">{{ paperlessSuggestion.raw }}</pre>
              </div>
              <div v-if="paperlessSuggestion.data">
                <div class="detail__suggestions__row">
                  <span>Summary:</span>
                  <div class="detail__suggestions__value">{{ paperlessSuggestion.data.summary }}</div>
                </div>
                <div class="detail__suggestions__row">
                  <span>Document type:</span>
                  <div class="detail__suggestions__value">{{ paperlessSuggestion.data.documentType || paperlessSuggestion.data.suggested_document_type }}</div>
                </div>
                <div class="detail__suggestions__row">
                  <span>Language:</span>
                  <div class="detail__suggestions__value">{{ paperlessSuggestion.data.language }}</div>
                </div>
                <div v-for="field in suggestionFields" :key="`paperless-${field.key}`" class="detail__suggestions__row">
                  <span>{{ field.label }}:</span>
                  <div class="detail__suggestions__value">{{ fieldValue(paperlessSuggestion.data, field.key) }}</div>
                  <button
                    class="detail__suggestions__button"
                    :disabled="suggestionVariantLoading[`paperless_ocr:${field.key}`]"
                    @click="suggestField('paperless_ocr', field.key)"
                  >
                    Suggest new
                  </button>
                </div>
                <div
                  v-if="(paperlessSuggestion.data.suggested_tags_existing || []).length || (paperlessSuggestion.data.suggested_tags_new || []).length"
                  class="detail__suggestions__tag-hints"
                >
                  <div>Existing tags: {{ (paperlessSuggestion.data.suggested_tags_existing || []).join(', ') }}</div>
                  <div>New tags: {{ (paperlessSuggestion.data.suggested_tags_new || []).join(', ') }}</div>
                </div>
                <div
                  v-for="field in suggestionFields"
                  :key="`paperless-variants-${field.key}`"
                  class="detail__suggestions__variants"
                >
                  <div v-if="suggestionVariantError[`paperless_ocr:${field.key}`]" class="detail__suggestions__error">
                    {{ suggestionVariantError[`paperless_ocr:${field.key}`] }}
                  </div>
                  <div v-if="(suggestionVariants[`paperless_ocr:${field.key}`] || []).length">
                    <div class="detail__suggestions__variants-title">Variants for {{ field.label }}</div>
                    <div
                      v-for="variant in suggestionVariants[`paperless_ocr:${field.key}`]"
                      :key="`${field.key}-${variant}`"
                      class="detail__suggestions__variant"
                    >
                      <span>{{ Array.isArray(variant) ? variant.join(', ') : variant }}</span>
                      <button
                        class="detail__suggestions__button"
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
          <div class="detail__suggestions__column">
            <div class="detail__suggestions__column-header">
              <strong>Vision OCR</strong>
              <button :disabled="suggestionsLoading" @click="refreshSuggestions('vision_ocr')">
                Refresh
              </button>
            </div>
            <div v-if="!visionSuggestion"><em>No data.</em></div>
            <div v-else>
              <div v-if="visionSuggestion.raw">
                <strong>Raw output</strong>
                <pre class="detail__suggestions__raw">{{ visionSuggestion.raw }}</pre>
              </div>
              <div v-if="visionSuggestion.data">
                <div class="detail__suggestions__row">
                  <span>Summary:</span>
                  <div class="detail__suggestions__value">{{ visionSuggestion.data.summary }}</div>
                </div>
                <div class="detail__suggestions__row">
                  <span>Document type:</span>
                  <div class="detail__suggestions__value">{{ visionSuggestion.data.documentType || visionSuggestion.data.suggested_document_type }}</div>
                </div>
                <div class="detail__suggestions__row">
                  <span>Language:</span>
                  <div class="detail__suggestions__value">{{ visionSuggestion.data.language }}</div>
                </div>
                <div v-for="field in suggestionFields" :key="`vision-${field.key}`" class="detail__suggestions__row">
                  <span>{{ field.label }}:</span>
                  <div class="detail__suggestions__value">{{ fieldValue(visionSuggestion.data, field.key) }}</div>
                  <button
                    class="detail__suggestions__button"
                    :disabled="suggestionVariantLoading[`vision_ocr:${field.key}`]"
                    @click="suggestField('vision_ocr', field.key)"
                  >
                    Suggest new
                  </button>
                </div>
                <div
                  v-if="(visionSuggestion.data.suggested_tags_existing || []).length || (visionSuggestion.data.suggested_tags_new || []).length"
                  class="detail__suggestions__tag-hints"
                >
                  <div>Existing tags: {{ (visionSuggestion.data.suggested_tags_existing || []).join(', ') }}</div>
                  <div>New tags: {{ (visionSuggestion.data.suggested_tags_new || []).join(', ') }}</div>
                </div>
                <div
                  v-for="field in suggestionFields"
                  :key="`vision-variants-${field.key}`"
                  class="detail__suggestions__variants"
                >
                  <div v-if="suggestionVariantError[`vision_ocr:${field.key}`]" class="detail__suggestions__error">
                    {{ suggestionVariantError[`vision_ocr:${field.key}`] }}
                  </div>
                  <div v-if="(suggestionVariants[`vision_ocr:${field.key}`] || []).length">
                    <div class="detail__suggestions__variants-title">Variants for {{ field.label }}</div>
                    <div
                      v-for="variant in suggestionVariants[`vision_ocr:${field.key}`]"
                      :key="`${field.key}-${variant}`"
                      class="detail__suggestions__variant"
                    >
                      <span>{{ Array.isArray(variant) ? variant.join(', ') : variant }}</span>
                      <button
                        class="detail__suggestions__button"
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
          <div class="detail__suggestions__column">
            <div class="detail__suggestions__column-header">
              <strong>Best pick</strong>
            </div>
            <div v-if="!bestPickSuggestion"><em>No data.</em></div>
            <div v-else>
              <div v-if="bestPickSuggestion.raw">
                <strong>Raw output</strong>
                <pre class="detail__suggestions__raw">{{ bestPickSuggestion.raw }}</pre>
              </div>
              <div v-if="bestPickSuggestion.data">
                <div class="detail__suggestions__row">
                  <span>Summary:</span>
                  <div class="detail__suggestions__value">{{ bestPickSuggestion.data.summary }}</div>
                </div>
                <div class="detail__suggestions__row">
                  <span>Document type:</span>
                  <div class="detail__suggestions__value">{{ bestPickSuggestion.data.documentType }}</div>
                </div>
                <div class="detail__suggestions__row">
                  <span>Language:</span>
                  <div class="detail__suggestions__value">{{ bestPickSuggestion.data.language }}</div>
                </div>
                <div v-for="field in suggestionFields" :key="`best-${field.key}`" class="detail__suggestions__row">
                  <span>{{ field.label }}:</span>
                  <div class="detail__suggestions__value">{{ fieldValue(bestPickSuggestion.data, field.key) }}</div>
                </div>
                <div
                  v-if="(bestPickSuggestion.data.suggested_tags_existing || []).length || (bestPickSuggestion.data.suggested_tags_new || []).length"
                  class="detail__suggestions__tag-hints"
                >
                  <div>Existing tags: {{ (bestPickSuggestion.data.suggested_tags_existing || []).join(', ') }}</div>
                  <div>New tags: {{ (bestPickSuggestion.data.suggested_tags_new || []).join(', ') }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="detail__page-texts">
        <div class="detail__page-texts__header">
          <h3>Extracted page texts (debug)</h3>
        </div>
        <div v-if="pageTextsError" class="detail__page-texts__error">
          {{ pageTextsError }}
        </div>
        <div v-else-if="pageTexts.length === 0">
          <em>No extracted page text loaded.</em>
        </div>
        <div v-else class="detail__page-texts__list">
          <div v-for="page in pageTexts" :key="page.page" class="detail__page-texts__item">
            <div class="detail__page-texts__meta">
              Page {{ page.page }} · Source: {{ page.source }}
            </div>
            <div v-if="page.quality" class="detail__page-texts__quality">
              <div class="detail__page-texts__quality-score">
                Quality score: {{ page.quality.score }}
              </div>
              <div v-if="page.quality.reasons?.length" class="detail__page-texts__quality-reasons">
                Reasons: {{ page.quality.reasons.join(', ') }}
              </div>
              <div class="detail__page-texts__quality-metrics">
                <div
                  v-for="(value, key) in page.quality.metrics"
                  :key="key"
                  class="detail__page-texts__quality-metric"
                >
                  {{ key }}: {{ value.toFixed ? value.toFixed(3) : value }}
                </div>
              </div>
            </div>
            <textarea class="detail__page-texts__text" readonly :value="page.text"></textarea>
          </div>
        </div>
      </div>
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

const fieldValue = (data: any, field: string) => {
  if (!data) return '';
  if (field === 'title') return data.title || data.suggested_title || '';
  if (field === 'date') return data.date || data.suggested_document_date || '';
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
    { label: 'Document date', value: document.value.document_date },
    { label: 'Created', value: document.value.created },
    { label: 'Modified', value: document.value.modified },
    { label: 'Correspondent', value: correspondentName },
    { label: 'Document type', value: docTypeName },
    { label: 'Tags', value: tagNames },
    { label: 'Original filename', value: document.value.original_file_name },
    { label: 'Notes', value: notes },
  ];
});

const load = async () => {
  loading.value = true;
  const { data } = await api.get<DocumentDetail>(`/documents/${id}`);
  document.value = data;
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

<style scoped>
.detail__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.detail__actions {
  display: flex;
  gap: 8px;
}
.detail__reprocess {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  margin-bottom: 16px;
}
.detail__reprocess__controls {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
}
.detail__table {
  width: 100%;
  border-collapse: collapse;
  background: white;
  border: 1px solid #e2e8f0;
  margin-bottom: 16px;
}
.detail__table th,
.detail__table td {
  padding: 8px 10px;
  border-bottom: 1px solid #e2e8f0;
  text-align: left;
}
.detail__text {
  width: 100%;
  min-height: 320px;
}
.detail__text-quality {
  margin-top: 12px;
  padding: 10px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
}
.detail__text-quality__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.detail__text-quality__error {
  color: #b91c1c;
  margin-bottom: 6px;
}
.detail__text-quality__body {
  font-size: 12px;
  color: #334155;
}
.detail__text-quality__score {
  font-weight: 600;
}
.detail__text-quality__reasons {
  margin-top: 4px;
}
.detail__text-quality__metrics {
  margin-top: 6px;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 4px 12px;
}
.detail__text-quality__metric {
  color: #475569;
}
.detail__suggestions {
  margin-top: 16px;
  padding: 10px;
  border: 1px solid #e2e8f0;
  background: #ffffff;
}
.detail__suggestions__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.detail__suggestions__error {
  color: #b91c1c;
  margin-bottom: 6px;
}
.detail__suggestions__body {
  font-size: 12px;
  color: #334155;
}
.detail__suggestions__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 12px;
}
.detail__suggestions__column {
  border: 1px solid #e2e8f0;
  padding: 8px;
  background: #f8fafc;
}
.detail__suggestions__column-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.detail__suggestions__row {
  display: grid;
  grid-template-columns: 160px 1fr auto;
  gap: 8px;
  padding: 4px 0;
  border-bottom: 1px solid #e2e8f0;
}
.detail__suggestions__row:last-child {
  border-bottom: none;
}
.detail__suggestions__value {
  color: #111827;
}
.detail__suggestions__raw {
  white-space: pre-wrap;
  background: #f8fafc;
  padding: 8px;
  border: 1px solid #e2e8f0;
}
.detail__suggestions__parsed {
  margin-top: 8px;
}
.detail__suggestions__button {
  background: #e2e8f0;
  border: 1px solid #cbd5f5;
  padding: 2px 6px;
  border-radius: 6px;
  cursor: pointer;
}
.detail__suggestions__button:hover {
  background: #cbd5f5;
}
.detail__suggestions__variants {
  margin: 6px 0 10px 0;
  padding: 6px;
  border: 1px dashed #cbd5e1;
  background: #f8fafc;
}
.detail__suggestions__variants-title {
  font-size: 12px;
  color: #475569;
  margin-bottom: 4px;
}
.detail__suggestions__variant {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: center;
  margin-bottom: 4px;
}
.detail__suggestions__tag-hints {
  font-size: 12px;
  color: #475569;
  padding: 4px 0;
}
.detail__page-texts {
  margin-top: 24px;
}
.detail__page-texts__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.detail__page-texts__error {
  color: #b91c1c;
  margin-bottom: 8px;
}
.detail__page-texts__list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.detail__page-texts__item {
  border: 1px solid #e2e8f0;
  padding: 10px;
  background: #f8fafc;
}
.detail__page-texts__meta {
  font-size: 12px;
  color: #475569;
  margin-bottom: 6px;
}
.detail__page-texts__text {
  width: 100%;
  min-height: 120px;
}
.detail__page-texts__quality {
  margin-bottom: 8px;
  font-size: 12px;
  color: #334155;
}
.detail__page-texts__quality-score {
  font-weight: 600;
}
.detail__page-texts__quality-reasons {
  margin-top: 4px;
}
.detail__page-texts__quality-metrics {
  margin-top: 6px;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 4px 12px;
}
.detail__page-texts__quality-metric {
  color: #475569;
}
</style>
