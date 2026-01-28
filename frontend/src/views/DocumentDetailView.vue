<template>
  <section class="detail">
    <div class="detail__header">
      <h2>{{ document?.title || `Document ${id}` }}</h2>
      <div class="detail__actions">
        <a v-if="paperlessUrl" :href="paperlessUrl" target="_blank" rel="noopener">
          <button type="button">View in Paperless</button>
        </a>
        <button :disabled="syncing" @click="resync">
          {{ syncing ? 'Resyncing…' : 'Resync' }}
        </button>
        <button @click="load">Reload</button>
      </div>
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

const route = useRoute();
const id = Number(route.params.id);
const document = ref<DocumentDetail | null>(null);
const loading = ref(false);
const syncing = ref(false);
const paperlessBaseUrl = import.meta.env.VITE_PAPERLESS_BASE_URL || '';
const paperlessUrl = computed(() =>
  paperlessBaseUrl && document.value
    ? `${paperlessBaseUrl.replace(/\/$/, '')}/documents/${document.value.id}`
    : ''
);
const tags = ref<Tag[]>([]);
const correspondents = ref<Correspondent[]>([]);
const docTypes = ref<DocumentType[]>([]);

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
    await api.post(`/sync/documents/${id}`, undefined, { params: { embed: true, force_embed: true } });
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

onMounted(async () => {
  await load();
  await loadMeta();
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
</style>
