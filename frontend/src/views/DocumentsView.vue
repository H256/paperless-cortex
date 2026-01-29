<template>
  <section>
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-2xl font-semibold tracking-tight">Documents</h2>
        <p class="text-sm text-slate-500">Manage ingestion, embedding, and review analysis status.</p>
      </div>
      <div class="flex items-center gap-3">
        <div class="grid grid-cols-4 gap-x-3 gap-y-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600 shadow-sm">
          <div class="text-slate-500">Synced</div>
          <div class="font-semibold text-slate-900">{{ stats.total }}</div>
          <div class="text-slate-500">Queued</div>
          <div class="font-semibold text-indigo-600">{{ queueStatus.enabled ? (queueStatus.length ?? 0) : 0 }}</div>

          <div class="text-slate-500">Embeddings</div>
          <div class="font-semibold text-emerald-600">{{ stats.embeddings }}</div>
          <div class="text-slate-500">Vision OCR</div>
          <div class="font-semibold text-emerald-600">{{ stats.vision }}</div>

          <div class="text-slate-500">Suggestions</div>
          <div class="font-semibold text-emerald-600">{{ stats.suggestions }}</div>
          <div class="text-slate-500">Fully processed</div>
          <div class="font-semibold text-emerald-700">{{ stats.fully_processed }}</div>

          <div class="text-slate-500">Pending</div>
          <div class="font-semibold text-amber-600">{{ stats.unprocessed }}</div>
          <div class="text-slate-500">Processed*</div>
          <div class="font-semibold text-emerald-600">{{ stats.processed }}</div>
        </div>
        <div v-if="isProcessing" class="flex items-center gap-3 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600 shadow-sm">
          <svg
            class="h-4 w-4 animate-spin text-indigo-500"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
          >
            <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-opacity="0.2" />
            <path d="M22 12a10 10 0 0 1-10 10" />
          </svg>
          <div class="space-y-0.5">
            <div v-if="syncStatus.status === 'running'">
              Sync {{ syncStatus.processed }} / {{ syncStatus.total }} ({{ progressPercent }}%) · ETA {{ etaText }}
            </div>
            <div v-if="embedStatus.status === 'running'">
              {{ embedLabel }} {{ embedStatus.processed }} / {{ embedStatus.total }} ({{ embedPercent }}%) · ETA {{ embedEtaText }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <section class="mt-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div class="flex w-full flex-wrap items-center justify-end gap-3">
        <div class="flex items-center gap-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-600">
          <label class="inline-flex items-center gap-2">
            <input type="checkbox" v-model="pageOnly" />
            Current page only
          </label>
          <label class="inline-flex items-center gap-2">
            <input type="checkbox" v-model="incremental" />
            Incremental
          </label>
        </div>
        <button
          class="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-slate-800"
          :disabled="syncing || isProcessing"
          @click="sync"
          title="Sync documents into the local database"
        >
          <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 12a9 9 0 1 1-3.3-6.9" />
            <polyline points="21 3 21 9 15 9" />
          </svg>
          {{ syncing ? 'Syncing...' : 'Sync (DB)' }}
        </button>
        <button
          class="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500"
          :disabled="syncing || isProcessing"
          @click="reprocessFiltered"
          title="Reprocess all documents: sync + OCR/embeddings"
        >
          <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M4 4v6h6" />
            <path d="M20 20v-6h-6" />
            <path d="M4 10a8 8 0 0 1 14.9-3" />
            <path d="M20 14a8 8 0 0 1-14.9 3" />
          </svg>
          Re-process filtered
        </button>
        <button
          class="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 shadow-sm hover:border-slate-300"
          :disabled="embedding || isProcessing"
          @click="reembedFiltered"
          title="Re-embed listed documents"
        >
          <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 3v6m0 6v6" />
            <path d="M3 12h6m6 0h6" />
          </svg>
          Re-embed filtered
        </button>
        <button
          class="inline-flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-800 shadow-sm hover:border-amber-300"
          :disabled="syncing || isProcessing"
          @click="reprocessMissing"
          title="Reprocess only documents missing embeddings and/or vision OCR (current list)"
        >
          <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 20h9" />
            <path d="M12 4h9" />
            <path d="M12 12h9" />
            <path d="M3 12l3 3 6-6" />
          </svg>
          Re-process missing
        </button>
        <button
          v-if="isProcessing"
          class="inline-flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm font-semibold text-rose-700 shadow-sm hover:border-rose-300"
          @click="cancelProcessing"
          title="Cancel processing and clear queued jobs"
        >
          <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="9" />
            <path d="M8 8l8 8M16 8l-8 8" />
          </svg>
          Cancel processing
        </button>
      </div>
    </section>

    <section class="mt-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <div class="text-xs font-semibold uppercase tracking-wide text-slate-400">Filters</div>
      <div class="grid gap-4 md:grid-cols-3 lg:grid-cols-6">
        <div>
          <label class="text-xs font-semibold text-slate-500">Sort</label>
          <select v-model="ordering" class="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-2 text-sm">
            <option value="-date">Date desc</option>
            <option value="date">Date asc</option>
            <option value="-title">Title desc</option>
            <option value="title">Title asc</option>
          </select>
        </div>
        <div>
          <label class="text-xs font-semibold text-slate-500">Correspondent</label>
          <select v-model="selectedCorrespondent" class="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-2 text-sm">
            <option value="">All</option>
            <option v-for="c in correspondents" :key="c.id" :value="String(c.id)">
              {{ c.name }}
            </option>
          </select>
        </div>
        <div>
          <label class="text-xs font-semibold text-slate-500">Tag</label>
          <select v-model="selectedTag" class="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-2 text-sm">
            <option value="">All</option>
            <option v-for="t in tags" :key="t.id" :value="String(t.id)">
              {{ t.name }}
            </option>
          </select>
        </div>
        <div>
          <label class="text-xs font-semibold text-slate-500">From</label>
          <input type="date" v-model="dateFrom" class="mt-1 w-full rounded-lg border border-slate-200 px-2 py-2 text-sm" />
        </div>
        <div>
          <label class="text-xs font-semibold text-slate-500">To</label>
          <input type="date" v-model="dateTo" class="mt-1 w-full rounded-lg border border-slate-200 px-2 py-2 text-sm" />
        </div>
        <div>
          <label class="text-xs font-semibold text-slate-500">Page size</label>
          <select v-model.number="pageSize" class="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-2 text-sm">
            <option :value="10">10</option>
            <option :value="20">20</option>
            <option :value="50">50</option>
          </select>
        </div>
      </div>

      <div class="mt-4 flex flex-wrap items-center gap-3 text-sm text-slate-600">
        <button class="ml-auto inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:border-slate-300" @click="load" title="Reload current list">
          <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 12a9 9 0 1 1-3.3-6.9" />
            <polyline points="21 3 21 9 15 9" />
          </svg>
          Reload
        </button>
      </div>
    </section>

    <section class="mt-6 rounded-xl border border-slate-200 bg-white shadow-sm">
      <div class="overflow-hidden">
        <table class="w-full border-collapse text-sm">
          <thead class="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
            <tr>
              <th class="px-6 py-3">
                <button class="inline-flex items-center gap-1" type="button" @click.stop="toggleSort('title')">
                  Title
                  <svg
                    v-if="sortDir('title')"
                    class="h-3 w-3 text-slate-400"
                    :class="{ 'rotate-180': sortDir('title') === 'desc' }"
                    viewBox="0 0 20 20"
                    fill="currentColor"
                  >
                    <path d="M10 4l5 6H5l5-6z" />
                  </svg>
                </button>
              </th>
              <th class="px-6 py-3">
                <button class="inline-flex items-center gap-1" type="button" @click.stop="toggleSort('date')">
                  Date
                  <svg
                    v-if="sortDir('date')"
                    class="h-3 w-3 text-slate-400"
                    :class="{ 'rotate-180': sortDir('date') === 'desc' }"
                    viewBox="0 0 20 20"
                    fill="currentColor"
                  >
                    <path d="M10 4l5 6H5l5-6z" />
                  </svg>
                </button>
              </th>
              <th class="px-6 py-3">Correspondent</th>
              <th class="px-6 py-3">Links</th>
              <th class="px-6 py-3">Status</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="doc in documents"
              :key="doc.id"
              class="border-b border-slate-100 hover:bg-slate-50"
              @click="open(doc.id)"
            >
              <td class="px-6 py-3 text-slate-900">{{ doc.title }}</td>
              <td class="px-6 py-3 text-slate-600">{{ formatDate(doc.document_date || doc.created) }}</td>
              <td class="px-6 py-3 text-slate-600">{{ correspondentLabel(doc.correspondent, doc.correspondent_name) }}</td>
              <td class="px-6 py-3 text-slate-600">
                <a
                  v-if="paperlessBaseUrl"
                  class="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-semibold text-slate-600 hover:border-slate-300"
                  :href="paperlessDocUrl(doc.id)"
                  target="_blank"
                  rel="noopener"
                  @click.stop
                >
                  <svg class="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M14 3h7v7" />
                    <path d="M10 14L21 3" />
                    <path d="M5 7v14h14v-7" />
                  </svg>
                </a>
              </td>
              <td class="px-6 py-3">
                <span
                  v-if="!hasDerived(doc)"
                  class="inline-flex items-center rounded-full bg-rose-50 px-3 py-1 text-xs font-semibold text-rose-700"
                >
                  No analysis
                </span>
                <span
                  v-else
                  class="inline-flex items-center rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700"
                >
                  Analyzed
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="flex items-center justify-between px-6 py-4 text-sm text-slate-600">
        <button class="rounded-lg border border-slate-200 bg-white px-4 py-2 font-semibold text-slate-700 shadow-sm" :disabled="page <= 1" @click="page -= 1; load()">Prev</button>
        <div class="text-center">
          <div class="text-sm font-semibold text-slate-700">Page {{ page }} of {{ totalPages }}</div>
          <div class="text-xs text-slate-400">Last synced: {{ formatDateTime(lastSynced) }}</div>
        </div>
        <button class="rounded-lg border border-slate-200 bg-white px-4 py-2 font-semibold text-slate-700 shadow-sm" :disabled="page >= totalPages" @click="page += 1; load()">Next</button>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
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
const queueStatus = ref<{ enabled: boolean; length: number | null; total?: number; in_progress?: number; done?: number }>({
  enabled: false,
  length: null,
});
const stats = ref({
  total: 0,
  processed: 0,
  unprocessed: 0,
  embeddings: 0,
  vision: 0,
  suggestions: 0,
  fully_processed: 0,
});
const paperlessBaseUrl = ref(import.meta.env.VITE_PAPERLESS_BASE_URL || '');
const paperlessDocUrl = (id: number) => {
  if (!paperlessBaseUrl.value) return '';
  return `${paperlessBaseUrl.value.replace(/\/$/, '')}/documents/${id}`;
};
let pollHandle: number | null = null;

const startPolling = () => {
  if (pollHandle !== null) return;
  pollHandle = window.setInterval(async () => {
    await fetchSyncStatus();
    await fetchEmbedStatus();
    await fetchQueueStatus();
    await fetchStats();
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
const isProcessing = computed(() =>
  syncStatus.value.status === 'running' || embedStatus.value.status === 'running'
);
const embedLabel = computed(() => {
  if (queueStatus.value.enabled && (queueStatus.value.length || queueStatus.value.in_progress)) {
    return 'Queue';
  }
  return 'Embed';
});
const sortDir = (field: string) => {
  const current = ordering.value.replace('-', '');
  if (current !== field) return null;
  return ordering.value.startsWith('-') ? 'desc' : 'asc';
};

const toggleSort = (field: string) => {
  const dir = sortDir(field);
  if (!dir || dir === 'desc') {
    ordering.value = field;
  } else {
    ordering.value = `-${field}`;
  }
  page.value = 1;
};
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
  await fetchStats();
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

const reprocessFiltered = async () => {
  syncing.value = true;
  startPolling();
  try {
    const ids = documents.value.map((doc) => doc.id);
    for (const docId of ids) {
      await api.post(`/sync/documents/${docId}`, undefined, {
        params: { embed: true, force_embed: true },
      });
    }
    await fetchSyncStatus();
    await fetchEmbedStatus();
    await load();
  } finally {
    syncing.value = false;
  }
};

const reembedCurrent = async () => {
  // legacy (unused)

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

const reembedFiltered = async () => {
  embedding.value = true;
  startPolling();
  try {
    const ids = documents.value.map((doc) => doc.id);
    await api.post('/embeddings/ingest-docs', ids, { params: { force: !incremental.value } });
    await fetchEmbedStatus();
  } finally {
    embedding.value = false;
  }
};

const reprocessMissing = async () => {
  syncing.value = true;
  startPolling();
  try {
    const missing = documents.value.filter(
      (doc) => !doc.has_embeddings || !doc.has_vision_pages
    );
    for (const doc of missing) {
      await api.post(`/sync/documents/${doc.id}`, undefined, {
        params: {
          embed: true,
          force_embed: true,
        },
      });
    }
    await fetchSyncStatus();
    await fetchEmbedStatus();
    await load();
  } finally {
    syncing.value = false;
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

const fetchQueueStatus = async () => {
  try {
    const { data } = await api.get<{ enabled: boolean; length: number | null; total?: number; in_progress?: number; done?: number }>(
      '/queue/status'
    );
    queueStatus.value = data;
  } catch {
    queueStatus.value = { enabled: false, length: null };
  }
};

const fetchStats = async () => {
  try {
    const { data } = await api.get<{
      total: number;
      processed: number;
      unprocessed: number;
      embeddings: number;
      vision: number;
      suggestions: number;
      fully_processed: number;
    }>('/documents/stats');
    stats.value = data;
  } catch {
    stats.value = {
      total: 0,
      processed: 0,
      unprocessed: 0,
      embeddings: 0,
      vision: 0,
      suggestions: 0,
      fully_processed: 0,
    };
  }
};

const fetchPaperlessBaseUrl = async () => {
  if (paperlessBaseUrl.value) return;
  try {
    const { data } = await api.get<{ paperless_base_url?: string }>('/status');
    if (data.paperless_base_url) {
      paperlessBaseUrl.value = data.paperless_base_url;
    }
  } catch {
    // ignore
  }
};
const cancelSync = async () => {
  await api.post('/sync/documents/cancel');
  await fetchSyncStatus();
};

const cancelProcessing = async () => {
  await api.post('/sync/documents/cancel');
  await api.post('/embeddings/cancel');
  await api.post('/queue/clear');
  await fetchSyncStatus();
  await fetchEmbedStatus();
  await fetchQueueStatus();
  await load();
  await fetchStats();
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

const formatDate = (value?: string | null) => {
  if (!value) return '';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat(navigator.language).format(parsed);
};

const formatDateTime = (value?: string | null) => {
  if (!value) return 'never';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat(navigator.language, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(parsed);
};

onMounted(async () => {
  await loadMeta();
  await fetchSyncStatus();
  await fetchEmbedStatus();
  await fetchQueueStatus();
  await fetchStats();
  await fetchPaperlessBaseUrl();
  await load();
  startPolling();
});

watch(ordering, async () => {
  await load();
});
</script>
