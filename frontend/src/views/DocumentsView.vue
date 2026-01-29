<template>
  <section>
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-2xl font-semibold tracking-tight">Documents</h2>
        <p class="text-sm text-slate-500">Manage ingestion, embedding, and review analysis status.</p>
      </div>
      <div class="flex items-center gap-2">
        <button
          class="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-slate-800"
          :disabled="syncing"
          @click="sync"
        >
          <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 12a9 9 0 1 1-3.3-6.9" />
            <polyline points="21 3 21 9 15 9" />
          </svg>
          {{ syncing ? 'Syncing...' : 'Sync (DB)' }}
        </button>
        <button
          class="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500"
          :disabled="syncing"
          @click="reprocessAll"
        >
          <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M4 4v6h6" />
            <path d="M20 20v-6h-6" />
            <path d="M4 10a8 8 0 0 1 14.9-3" />
            <path d="M20 14a8 8 0 0 1-14.9 3" />
          </svg>
          Re-process all
        </button>
        <button
          class="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 shadow-sm hover:border-slate-300"
          :disabled="embedding"
          @click="reembedCurrent"
        >
          <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 3v6m0 6v6" />
            <path d="M3 12h6m6 0h6" />
          </svg>
          Re-embed current
        </button>
      </div>
    </div>

    <section class="mt-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <div class="grid gap-4 md:grid-cols-3 lg:grid-cols-6">
        <div>
          <label class="text-xs font-semibold text-slate-500">Sort</label>
          <select v-model="ordering" class="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-2 text-sm">
            <option value="-date">Date desc</option>
            <option value="date">Date asc</option>
            <option value="-title">Title desc</option>
            <option value="title">Title asc</option>
            <option value="-id">ID desc</option>
            <option value="id">ID asc</option>
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
        <label class="inline-flex items-center gap-2">
          <input type="checkbox" v-model="pageOnly" />
          Current page only
        </label>
        <label class="inline-flex items-center gap-2">
          <input type="checkbox" v-model="incremental" />
          Incremental
        </label>
        <button class="ml-auto inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:border-slate-300" @click="load">
          <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 12a9 9 0 1 1-3.3-6.9" />
            <polyline points="21 3 21 9 15 9" />
          </svg>
          Reload
        </button>
      </div>
    </section>

    <section class="mt-6 rounded-xl border border-slate-200 bg-white shadow-sm">
      <div class="border-b border-slate-200 px-6 py-4 text-sm text-slate-600">
        <span>Last synced: {{ lastSynced ?? 'never' }}</span>
        <span v-if="syncStatus.status === 'running'" class="ml-4">Sync: {{ syncStatus.processed }} / {{ syncStatus.total }} ({{ progressPercent }}%) - ETA: {{ etaText }}</span>
        <span v-if="embedStatus.status === 'running'" class="ml-4">Embed: {{ embedStatus.processed }} / {{ embedStatus.total }} ({{ embedPercent }}%) - ETA: {{ embedEtaText }}</span>
      </div>
      <div class="overflow-hidden">
        <table class="w-full border-collapse text-sm">
          <thead class="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
            <tr>
              <th class="px-6 py-3">
                <button class="inline-flex items-center gap-1" type="button" @click.stop="toggleSort('id')">
                  ID
                  <svg
                    v-if="sortDir('id')"
                    class="h-3 w-3 text-slate-400"
                    :class="{ 'rotate-180': sortDir('id') === 'desc' }"
                    viewBox="0 0 20 20"
                    fill="currentColor"
                  >
                    <path d="M10 4l5 6H5l5-6z" />
                  </svg>
                </button>
              </th>
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
              <td class="px-6 py-3 font-medium text-slate-900">{{ doc.id }}</td>
              <td class="px-6 py-3 text-slate-900">{{ doc.title }}</td>
              <td class="px-6 py-3 text-slate-600">{{ formatDate(doc.document_date || doc.created) }}</td>
              <td class="px-6 py-3 text-slate-600">{{ correspondentLabel(doc.correspondent, doc.correspondent_name) }}</td>
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
        <button class="rounded-lg border border-slate-200 bg-white px-3 py-2" :disabled="page <= 1" @click="page -= 1; load()">Prev</button>
        <span>Page {{ page }} of {{ totalPages }}</span>
        <button class="rounded-lg border border-slate-200 bg-white px-3 py-2" :disabled="page >= totalPages" @click="page += 1; load()">Next</button>
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
let pollHandle: number | null = null;

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

onMounted(async () => {
  await loadMeta();
  await fetchSyncStatus();
  await fetchEmbedStatus();
  await load();
  startPolling();
});

watch(ordering, async () => {
  await load();
});
</script>
