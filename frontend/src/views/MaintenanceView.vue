<template>
  <section>
    <div class="flex flex-wrap items-center justify-between gap-4">
      <div>
        <h2 class="text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">Operations</h2>
        <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Operational controls for resets, cleanup, and runtime inspection.
        </p>
      </div>
    </div>

    <section class="mt-6 rounded-xl border border-rose-200 bg-white p-6 shadow-sm dark:border-rose-900/50 dark:bg-slate-900">
      <div class="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h3 class="text-lg font-semibold text-rose-700 dark:text-rose-300">Reprocess all documents</h3>
          <p class="text-sm text-slate-500 dark:text-slate-400">
            Clears all intelligence data and rebuilds everything from scratch.
          </p>
        </div>
        <button
          class="inline-flex items-center gap-2 rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-rose-500"
          :disabled="syncing || isProcessing"
          @click="openReprocessModal"
        >
          <RefreshCcw class="h-4 w-4" />
          Reprocess all
        </button>
      </div>
      <div class="mt-4 rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-200">
        This action cannot be undone. Paperless data is not modified.
      </div>
    </section>

    <section class="mt-6 grid gap-4 lg:grid-cols-3">
      <div class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <h3 class="text-lg font-semibold text-slate-900 dark:text-slate-100">Remove Vision OCR</h3>
        <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Deletes all stored vision OCR pages. Documents will need OCR again.
        </p>
        <div class="mt-4 flex items-center gap-3">
          <button
            class="rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-sm font-semibold text-rose-700 hover:border-rose-300 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-200"
            :disabled="visionLoading"
            @click="confirmVision"
          >
            <span v-if="visionLoading" class="inline-flex items-center gap-2">
              <Loader2 class="h-4 w-4 animate-spin" />
              Removing...
            </span>
            <span v-else>Remove vision OCR</span>
          </button>
          <div v-if="visionResult" class="text-xs text-slate-500 dark:text-slate-400">
            Removed {{ visionResult.deleted }} rows
          </div>
        </div>
      </div>

      <div class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <h3 class="text-lg font-semibold text-slate-900 dark:text-slate-100">Remove Suggestions</h3>
        <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Deletes all AI suggestions across documents.
        </p>
        <div class="mt-4 flex items-center gap-3">
          <button
            class="rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-sm font-semibold text-rose-700 hover:border-rose-300 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-200"
            :disabled="suggestionsLoading"
            @click="confirmSuggestions"
          >
            <span v-if="suggestionsLoading" class="inline-flex items-center gap-2">
              <Loader2 class="h-4 w-4 animate-spin" />
              Removing...
            </span>
            <span v-else>Remove suggestions</span>
          </button>
          <div v-if="suggestionsResult" class="text-xs text-slate-500 dark:text-slate-400">
            Removed {{ suggestionsResult.deleted }} rows
          </div>
        </div>
      </div>

      <div class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <h3 class="text-lg font-semibold text-slate-900 dark:text-slate-100">Remove Embeddings</h3>
        <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Deletes all embeddings (paperless + vision) and clears Qdrant points.
        </p>
        <div class="mt-4 flex items-center gap-3">
          <button
            class="rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-sm font-semibold text-rose-700 hover:border-rose-300 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-200"
            :disabled="embeddingsLoading"
            @click="confirmEmbeddings"
          >
            <span v-if="embeddingsLoading" class="inline-flex items-center gap-2">
              <Loader2 class="h-4 w-4 animate-spin" />
              Removing...
            </span>
            <span v-else>Remove embeddings</span>
          </button>
          <div v-if="embeddingsResult" class="text-xs text-slate-500 dark:text-slate-400">
            Removed {{ embeddingsResult.deleted }} rows (Qdrant ok: {{ embeddingsResult.qdrant_deleted }}, errors: {{ embeddingsResult.qdrant_errors }})
          </div>
        </div>
      </div>
    </section>

    <section class="mt-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div class="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h3 class="text-lg font-semibold text-slate-900 dark:text-slate-100">Runtime Configuration</h3>
          <p class="text-sm text-slate-500 dark:text-slate-400">
            Read-only view of server URLs and models currently in use.
          </p>
        </div>
      </div>
      <div class="mt-4 grid gap-4 md:grid-cols-2">
        <div class="rounded-lg border border-slate-200 bg-slate-50 p-4 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-800 dark:text-slate-200">
          <div class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">URLs</div>
          <dl class="mt-3 space-y-2">
            <div class="flex items-center justify-between gap-4">
              <dt class="text-slate-500 dark:text-slate-400">Paperless</dt>
              <dd class="truncate text-right text-slate-900 dark:text-slate-100">{{ runtime.paperless_base_url || '—' }}</dd>
            </div>
            <div class="flex items-center justify-between gap-4">
              <dt class="text-slate-500 dark:text-slate-400">Ollama</dt>
              <dd class="truncate text-right text-slate-900 dark:text-slate-100">{{ runtime.ollama_base_url || '—' }}</dd>
            </div>
            <div class="flex items-center justify-between gap-4">
              <dt class="text-slate-500 dark:text-slate-400">Qdrant</dt>
              <dd class="truncate text-right text-slate-900 dark:text-slate-100">{{ runtime.qdrant_url || '—' }}</dd>
            </div>
            <div class="flex items-center justify-between gap-4">
              <dt class="text-slate-500 dark:text-slate-400">Redis</dt>
              <dd class="truncate text-right text-slate-900 dark:text-slate-100">{{ runtime.redis_host || '—' }}</dd>
            </div>
          </dl>
        </div>
        <div class="rounded-lg border border-slate-200 bg-slate-50 p-4 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-800 dark:text-slate-200">
          <div class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">Models</div>
          <dl class="mt-3 space-y-2">
            <div class="flex items-center justify-between gap-4">
              <dt class="text-slate-500 dark:text-slate-400">Ollama</dt>
              <dd class="truncate text-right text-slate-900 dark:text-slate-100">{{ runtime.ollama_model || '—' }}</dd>
            </div>
            <div class="flex items-center justify-between gap-4">
              <dt class="text-slate-500 dark:text-slate-400">Embeddings</dt>
              <dd class="truncate text-right text-slate-900 dark:text-slate-100">{{ runtime.embedding_model || '—' }}</dd>
            </div>
            <div class="flex items-center justify-between gap-4">
              <dt class="text-slate-500 dark:text-slate-400">Vision OCR</dt>
              <dd class="truncate text-right text-slate-900 dark:text-slate-100">{{ runtime.vision_model || '—' }}</dd>
            </div>
          </dl>
        </div>
      </div>
    </section>
  </section>

  <div v-if="showReprocessModal" class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4">
    <div class="w-full max-w-xl rounded-2xl border border-rose-200 bg-white p-6 shadow-xl dark:border-rose-900/50 dark:bg-slate-900">
      <div class="flex items-center justify-between">
        <div>
          <h3 class="text-lg font-semibold text-rose-700">Reprocess all documents?</h3>
          <p class="text-xs text-slate-500 dark:text-slate-400">
            This wipes all intelligence data (embeddings, suggestions, OCR layers) and rebuilds from scratch.
          </p>
        </div>
      </div>

      <div class="mt-4 rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-200">
        This action cannot be undone. Paperless data is not modified.
      </div>

      <div v-if="syncStatus.status === 'running'" class="mt-4 rounded-lg border border-indigo-200 bg-indigo-50 p-3 text-xs text-indigo-700 dark:border-indigo-900/50 dark:bg-indigo-950/40 dark:text-indigo-200">
        <div class="flex items-center gap-2">
          <Loader2 class="h-4 w-4 animate-spin" />
          Sync {{ syncStatus.processed }} / {{ syncStatus.total }} ({{ progressPercent }}%) - ETA {{ etaText }}
        </div>
      </div>

      <div class="mt-6 flex flex-wrap items-center justify-end gap-3">
        <button
          class="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
          @click="closeReprocessModal"
          :disabled="reprocessRunning"
        >
          Cancel
        </button>
        <button
          class="rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-rose-500"
          :disabled="syncing || isProcessing || reprocessRunning"
          @click="confirmReprocessAll"
        >
          <span v-if="reprocessRunning" class="inline-flex items-center gap-2">
            <Loader2 class="h-4 w-4 animate-spin" />
            Starting...
          </span>
          <span v-else>Yes, reprocess all</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { RefreshCcw, Loader2 } from 'lucide-vue-next';
import { storeToRefs } from 'pinia';
import { useDocumentsStore } from '../stores/documentsStore';
import { useStatusStore } from '../stores/statusStore';

const documentsStore = useDocumentsStore();
const statusStore = useStatusStore();

const { syncing, syncStatus, embedStatus } = storeToRefs(documentsStore);
const { runtime } = storeToRefs(statusStore);

const showReprocessModal = ref(false);
const reprocessRunning = ref(false);

const isProcessing = computed(() => syncStatus.value.status === 'running' || embedStatus.value.status === 'running');

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

const visionLoading = ref(false);
const suggestionsLoading = ref(false);
const embeddingsLoading = ref(false);
const visionResult = ref<{ deleted: number } | null>(null);
const suggestionsResult = ref<{ deleted: number } | null>(null);
const embeddingsResult = ref<{ deleted: number; qdrant_deleted: number; qdrant_errors: number } | null>(null);

const openReprocessModal = () => {
  showReprocessModal.value = true;
};

const closeReprocessModal = () => {
  showReprocessModal.value = false;
};

const confirmReprocessAll = async () => {
  reprocessRunning.value = true;
  try {
    await documentsStore.reprocessAll();
    await queueStore.refreshStatus();
    showReprocessModal.value = false;
  } finally {
    reprocessRunning.value = false;
  }
};

const confirmVision = async () => {
  const ok = window.confirm('Remove all vision OCR pages for every document? This cannot be undone.');
  if (!ok) return;
  visionLoading.value = true;
  visionResult.value = null;
  try {
    const result = await documentsStore.removeVisionOcr();
    visionResult.value = { deleted: result.deleted ?? 0 };
  } finally {
    visionLoading.value = false;
  }
};

const confirmSuggestions = async () => {
  const ok = window.confirm('Remove all AI suggestions for every document? This cannot be undone.');
  if (!ok) return;
  suggestionsLoading.value = true;
  suggestionsResult.value = null;
  try {
    const result = await documentsStore.removeSuggestions();
    suggestionsResult.value = { deleted: result.deleted ?? 0 };
  } finally {
    suggestionsLoading.value = false;
  }
};

const confirmEmbeddings = async () => {
  const ok = window.confirm('Remove all embeddings (paperless + vision) for every document? This cannot be undone.');
  if (!ok) return;
  embeddingsLoading.value = true;
  embeddingsResult.value = null;
  try {
    const result = await documentsStore.removeEmbeddings();
    embeddingsResult.value = {
      deleted: result.deleted ?? 0,
      qdrant_deleted: result.qdrant_deleted ?? 0,
      qdrant_errors: result.qdrant_errors ?? 0,
    };
  } finally {
    embeddingsLoading.value = false;
  }
};

onMounted(async () => {
  await statusStore.refresh();
});
</script>
