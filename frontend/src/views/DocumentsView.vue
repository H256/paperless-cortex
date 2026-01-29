<template>
  <section class="documents">
    <div class="documents__header">
      <h2>Documents</h2>
      <div class="documents__controls">
        <button :disabled="syncing" @click="sync">
          {{ syncing ? 'Syncing...' : 'Sync (DB only)' }}
        </button>
        <button :disabled="syncing" @click="reprocessAll">
          Reprocess all (sync + embed)
        </button>
        <button :disabled="embedding" @click="reembedCurrent">
          Re-embed current
        </button>
        <button v-if="syncStatus.status === 'running'" @click="cancelSync">
          Cancel sync
        </button>
        <label>
          Current page only
          <input type="checkbox" v-model="pageOnly" />
        </label>
        <label>
          Incremental
          <input type="checkbox" v-model="incremental" />
        </label>
        <label>
          Sort
          <select v-model="ordering">
            <option value="-date">Date desc</option>
            <option value="date">Date asc</option>
            <option value="-title">Title desc</option>
            <option value="title">Title asc</option>
            <option value="-id">ID desc</option>
            <option value="id">ID asc</option>
          </select>
        </label>
        <label>
          Correspondent
          <select v-model="selectedCorrespondent">
            <option value="">All</option>
            <option v-for="c in correspondents" :key="c.id" :value="String(c.id)">
              {{ c.name }}
            </option>
          </select>
        </label>
        <label>
          Tag
          <select v-model="selectedTag">
            <option value="">All</option>
            <option v-for="t in tags" :key="t.id" :value="String(t.id)">
              {{ t.name }}
            </option>
          </select>
        </label>
        <label>
          From
          <input type="date" v-model="dateFrom" />
        </label>
        <label>
          To
          <input type="date" v-model="dateTo" />
        </label>
        <label>
          Page size
          <select v-model.number="pageSize">
            <option :value="10">10</option>
            <option :value="20">20</option>
            <option :value="50">50</option>
          </select>
        </label>
        <button @click="load">Reload</button>
      </div>
    </div>
    <div class="documents__search">
      <div class="documents__search__header">
        <h3>Semantic search</h3>
        <div class="documents__search__controls">
          <input
            v-model="searchQuery"
            class="documents__search__input"
            type="text"
            placeholder="Ask a question or search..."
            @keyup.enter="runSearch"
          />
          <label>
            Top K
            <select v-model.number="searchTopK">
              <option :value="5">5</option>
              <option :value="10">10</option>
              <option :value="20">20</option>
            </select>
          </label>
          <label>
            Source
            <select v-model="searchSource">
              <option value="">All</option>
              <option value="vision_ocr">Vision OCR</option>
              <option value="paperless_ocr">Paperless OCR</option>
              <option value="pdf_text">PDF text</option>
            </select>
          </label>
          <label>
            Only vision OCR
            <input type="checkbox" v-model="searchOnlyVision" />
          </label>
          <label>
            Dedupe
            <input type="checkbox" v-model="searchDedupe" />
          </label>
          <label>
            Rerank
            <input type="checkbox" v-model="searchRerank" />
          </label>
          <label>
            Min quality: {{ searchMinQuality }}
            <input type="range" min="0" max="100" v-model.number="searchMinQuality" />
          </label>
          <button :disabled="searchLoading || !searchQuery" @click="runSearch">
            {{ searchLoading ? 'Searching...' : 'Search' }}
          </button>
        </div>
      </div>
      <div v-if="searchError" class="documents__search__error">{{ searchError }}</div>
      <div v-else-if="searchResults.length === 0">
        <em>No results yet.</em>
      </div>
      <div v-else class="documents__search__results">
        <div
          v-for="result in filteredSearchResults"
          :key="`${result.doc_id}-${result.page}-${result.source}`"
          class="documents__search__result"
          @click="open(result.doc_id)"
        >
          <div class="documents__search__meta">
            Doc {{ result.doc_id }} · Page {{ result.page ?? 'n/a' }} ·
            {{ result.source || 'unknown' }} ·
            Score {{ result.score?.toFixed ? result.score.toFixed(3) : result.score }} ·
            Quality {{ result.quality_score }}
          </div>
          <div v-if="result.document" class="documents__search__doc">
            <strong>{{ result.document.title || `Document ${result.doc_id}` }}</strong>
            <span>
              · {{ result.document.document_date || result.document.created || 'n/a' }}
            </span>
            <span v-if="result.document.correspondent_name">
              · {{ result.document.correspondent_name }}
            </span>
            <a
              v-if="paperlessBaseUrl"
              class="documents__search__paperless"
              :href="`${paperlessBaseUrl.replace(/\/$/, '')}/documents/${result.doc_id}`"
              target="_blank"
              rel="noopener"
              @click.stop
            >
              Open in Paperless
            </a>
          </div>
          <div class="documents__search__snippet">{{ result.snippet }}</div>
        </div>
      </div>
    </div>
    <div class="documents__status">
      <span>Last synced: {{ lastSynced ?? 'never' }}</span>
      <span v-if="syncStatus.status === 'running'">
        Sync: {{ syncStatus.processed }} / {{ syncStatus.total }} ({{ progressPercent }}%)
        - ETA: {{ etaText }}
      </span>
      <span v-if="embedStatus.status === 'running'">
        Embed: {{ embedStatus.processed }} / {{ embedStatus.total }} ({{ embedPercent }}%)
        - ETA: {{ embedEtaText }}
      </span>
      <div v-if="syncStatus.status === 'running'" class="documents__progress" />
      <div v-if="embedStatus.status === 'running'" class="documents__progress documents__progress--embed" />
    </div>

    <table class="documents__table">
      <thead>
        <tr>
          <th>ID</th>
          <th>Title</th>
          <th>Date</th>
          <th>Correspondent</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="doc in documents" :key="doc.id" @click="open(doc.id)">
          <td>{{ doc.id }}</td>
          <td>{{ doc.title }}</td>
          <td>{{ doc.document_date || doc.created }}</td>
          <td>{{ correspondentLabel(doc.correspondent, doc.correspondent_name) }}</td>
          <td>
            <span v-if="!hasDerived(doc)" class="badge badge--warn">No analysis</span>
            <span v-else class="badge badge--ok">Analyzed</span>
          </td>
        </tr>
      </tbody>
    </table>

    <div class="documents__pagination">
      <button :disabled="page <= 1" @click="page -= 1; load()">Prev</button>
      <span>Page {{ page }} of {{ totalPages }}</span>
      <button :disabled="page >= totalPages" @click="page += 1; load()">Next</button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { api, Page } from '../api';

interface DocumentRow {
  id: number;
  title: string;
  document_date?: string | null;
  created?: string | null;
  correspondent?: number | null;
  correspondent_name?: string | null;
  has_embeddings?: boolean;
  has_suggestions?: boolean;
  has_vision_pages?: boolean;
}

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

interface Tag {
  id: number;
  name: string;
}

interface Correspondent {
  id: number;
  name: string;
}

const router = useRouter();
const documents = ref<DocumentRow[]>([]);
const page = ref(1);
const pageSize = ref(20);
const ordering = ref('-date');
const totalCount = ref(0);
const tags = ref<Tag[]>([]);
const correspondents = ref<Correspondent[]>([]);
const selectedTag = ref('');
const selectedCorrespondent = ref('');
const dateFrom = ref('');
const dateTo = ref('');
const syncing = ref(false);
const lastSynced = ref<string | null>(null);
const incremental = ref(true);
const pageOnly = ref(false);
const embedding = ref(false);
const syncStatus = ref({
  status: 'idle',
  processed: 0,
  total: 0,
  started_at: null as string | null,
  eta_seconds: null as number | null,
});
const embedStatus = ref({
  status: 'idle',
  processed: 0,
  total: 0,
  started_at: null as string | null,
  eta_seconds: null as number | null,
});
let pollHandle: number | null = null;
const searchQuery = ref('');
const searchTopK = ref(10);
const searchSource = ref('');
const searchResults = ref<SearchResult[]>([]);
const searchLoading = ref(false);
const searchError = ref('');
const searchDedupe = ref(true);
const searchRerank = ref(true);
const searchOnlyVision = ref(false);
const searchMinQuality = ref(0);
const paperlessBaseUrl = import.meta.env.VITE_PAPERLESS_BASE_URL || '';

const startPolling = () => {
  if (pollHandle !== null) return;
  pollHandle = window.setInterval(async () => {
    await fetchSyncStatus();
    await fetchEmbedStatus();
    if (syncStatus.value.status !== 'running' && embedStatus.value.status !== 'running') {
      if (pollHandle !== null) {
        window.clearInterval(pollHandle);
        pollHandle = null;
      }
    }
  }, 2000);
};

const totalPages = computed(() =>
  Math.max(1, Math.ceil(totalCount.value / pageSize.value))
);
const progressPercent = computed(() => {
  if (!syncStatus.value.total) return 0;
  return Math.min(100, Math.round((syncStatus.value.processed / syncStatus.value.total) * 100));
});
const etaText = computed(() => {
  if (syncStatus.value.eta_seconds !== null && syncStatus.value.eta_seconds !== undefined) {
    const minutes = Math.floor(syncStatus.value.eta_seconds / 60);
    const seconds = syncStatus.value.eta_seconds % 60;
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  }
  if (!syncStatus.value.started_at || !syncStatus.value.processed) return '--';
  const started = Date.parse(syncStatus.value.started_at);
  if (Number.isNaN(started)) return '--';
  const elapsedMs = Date.now() - started;
  const rate = syncStatus.value.processed / Math.max(1, elapsedMs / 1000);
  if (!syncStatus.value.total || rate <= 0) return '--';
  const remaining = syncStatus.value.total - syncStatus.value.processed;
  const etaSec = Math.max(0, Math.round(remaining / rate));
  const minutes = Math.floor(etaSec / 60);
  const seconds = etaSec % 60;
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
});
const embedPercent = computed(() => {
  if (!embedStatus.value.total) return 0;
  return Math.min(100, Math.round((embedStatus.value.processed / embedStatus.value.total) * 100));
});
const embedEtaText = computed(() => {
  if (embedStatus.value.eta_seconds !== null && embedStatus.value.eta_seconds !== undefined) {
    const minutes = Math.floor(embedStatus.value.eta_seconds / 60);
    const seconds = embedStatus.value.eta_seconds % 60;
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  }
  if (!embedStatus.value.started_at || !embedStatus.value.processed) return '--';
  const started = Date.parse(embedStatus.value.started_at);
  if (Number.isNaN(started)) return '--';
  const elapsedMs = Date.now() - started;
  const rate = embedStatus.value.processed / Math.max(1, elapsedMs / 1000);
  if (!embedStatus.value.total || rate <= 0) return '--';
  const remaining = embedStatus.value.total - embedStatus.value.processed;
  const etaSec = Math.max(0, Math.round(remaining / rate));
  const minutes = Math.floor(etaSec / 60);
  const seconds = etaSec % 60;
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
});
const effectiveSource = computed(() => {
  if (searchOnlyVision.value) return 'vision_ocr';
  return searchSource.value || '';
});
const filteredSearchResults = computed(() => {
  if (!effectiveSource.value) return searchResults.value;
  return searchResults.value.filter((result) => result.source === effectiveSource.value);
});

const load = async () => {
  const { data } = await api.get<Page<DocumentRow>>('/documents', {
    params: {
      page: page.value,
      page_size: pageSize.value,
      ordering: ordering.value,
      correspondent__id: selectedCorrespondent.value || undefined,
      tags__id: selectedTag.value || undefined,
      document_date__gte: dateFrom.value || undefined,
      document_date__lte: dateTo.value || undefined,
      include_derived: true,
    },
  });
  documents.value = data.results ?? [];
  totalCount.value = data.count ?? documents.value.length;
};

const sync = async () => {
  syncing.value = true;
  startPolling();
  try {
    await api.post('/sync/documents', undefined, {
      params: {
        page_size: pageSize.value,
        incremental: incremental.value,
        page: page.value,
        page_only: pageOnly.value,
      },
    });
    await fetchSyncStatus();
    await load();
  } finally {
    syncing.value = false;
  }
  if (pollHandle === null) {
    pollHandle = window.setInterval(async () => {
      await fetchSyncStatus();
      await fetchEmbedStatus();
      if (syncStatus.value.status !== 'running' && embedStatus.value.status !== 'running') {
        if (pollHandle !== null) {
          window.clearInterval(pollHandle);
          pollHandle = null;
        }
      }
    }, 2000);
  }
};

const reprocessAll = async () => {
  syncing.value = true;
  startPolling();
  try {
    await api.post('/sync/documents', undefined, {
      params: {
        page_size: pageSize.value,
        incremental: false,
        page_only: false,
        embed: true,
        force_embed: true,
      },
    });
    await fetchSyncStatus();
    await fetchEmbedStatus();
    await load();
  } finally {
    syncing.value = false;
  }
};

const reembedCurrent = async () => {
  embedding.value = true;
  startPolling();
  try {
    const force = !incremental.value;
    if (pageOnly.value) {
      const ids = documents.value.map((doc) => doc.id);
      await api.post('/embeddings/ingest-docs', ids, { params: { force } });
    } else {
      await api.post('/embeddings/ingest', undefined, { params: { force, limit: 0 } });
    }
    await fetchEmbedStatus();
  } finally {
    embedding.value = false;
  }
};

const fetchSyncStatus = async () => {
  const { data } = await api.get<{
    last_synced_at: string | null;
    status: string;
    processed: number;
    total: number;
    started_at: string | null;
    eta_seconds?: number | null;
  }>('/sync/documents');
  lastSynced.value = data.last_synced_at;
  syncStatus.value = data;
};

const fetchEmbedStatus = async () => {
  const { data } = await api.get<{
    status: string;
    processed: number;
    total: number;
    started_at: string | null;
    eta_seconds?: number | null;
  }>('/embeddings/status');
  embedStatus.value = data;
};

const cancelSync = async () => {
  await api.post('/sync/documents/cancel');
  await fetchSyncStatus();
};

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

const loadMeta = async () => {
  const [tagsResp, corrResp] = await Promise.all([
    api.get<Page<Tag>>('/tags', { params: { page: 1, page_size: 200 } }),
    api.get<Page<Correspondent>>('/correspondents', { params: { page: 1, page_size: 200 } }),
  ]);
  tags.value = tagsResp.data.results ?? [];
  correspondents.value = corrResp.data.results ?? [];
};

const open = (id: number) => {
  router.push(`/documents/${id}`);
};

const correspondentLabel = (id?: number | null, name?: string | null) => {
  if (name) return name;
  if (!id) return '';
  return correspondents.value.find((c) => c.id === id)?.name ?? String(id);
};

const hasDerived = (doc: DocumentRow) => {
  return Boolean(doc.has_embeddings || doc.has_suggestions || doc.has_vision_pages);
};

onMounted(async () => {
  await loadMeta();
  await fetchSyncStatus();
  await fetchEmbedStatus();
  await load();
  startPolling();
});
</script>

<style scoped>
.documents__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}
.documents__controls {
  display: flex;
  gap: 12px;
  align-items: center;
}
.documents__status {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  color: #475569;
  flex-wrap: wrap;
}
.documents__search {
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  padding: 12px;
  margin-bottom: 16px;
}
.documents__search__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.documents__search__controls {
  display: flex;
  gap: 10px;
  align-items: center;
}
.documents__search__input {
  min-width: 280px;
}
.documents__search__error {
  color: #b91c1c;
}
.documents__search__results {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.documents__search__result {
  padding: 8px;
  border: 1px solid #e2e8f0;
  background: #ffffff;
  cursor: pointer;
}
.documents__search__result:hover {
  background: #f1f5f9;
}
.documents__search__meta {
  font-size: 12px;
  color: #475569;
  margin-bottom: 4px;
}
.documents__search__doc {
  font-size: 13px;
  color: #111827;
  margin-bottom: 4px;
  display: flex;
  gap: 8px;
  align-items: baseline;
  flex-wrap: wrap;
}
.documents__search__paperless {
  font-size: 12px;
  color: #2563eb;
  text-decoration: none;
}
.documents__search__paperless:hover {
  text-decoration: underline;
}
.documents__search__snippet {
  color: #111827;
}
.documents__progress {
  position: relative;
  width: 200px;
  height: 4px;
  background: #e2e8f0;
  overflow: hidden;
  border-radius: 999px;
}
.documents__progress::after {
  content: "";
  position: absolute;
  left: -40%;
  width: 40%;
  height: 100%;
  background: #2563eb;
  animation: progress 1.2s infinite;
}
.documents__progress--embed::after {
  background: #16a34a;
}
.documents__table {
  width: 100%;
  border-collapse: collapse;
  background: white;
  border: 1px solid #e2e8f0;
}
.documents__table th,
.documents__table td {
  padding: 10px 12px;
  border-bottom: 1px solid #e2e8f0;
}
.documents__table tbody tr:hover {
  background: #f1f5f9;
  cursor: pointer;
}
.documents__pagination {
  margin-top: 12px;
  display: flex;
  gap: 12px;
  align-items: center;
}
.badge {
  display: inline-flex;
  padding: 2px 8px;
  font-size: 12px;
  border-radius: 999px;
}
.badge--ok {
  background: #dcfce7;
  color: #166534;
}
.badge--warn {
  background: #fee2e2;
  color: #991b1b;
}

@keyframes progress {
  0% { left: -40%; }
  50% { left: 30%; }
  100% { left: 100%; }
}
</style>
