<template>
  <section>
    <div class="flex flex-wrap items-center justify-between gap-4">
      <div>
        <h2 class="text-2xl font-semibold tracking-tight text-slate-900">Queue Manager</h2>
        <p class="mt-1 text-sm text-slate-500">Control processing order and check what is coming next.</p>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <button
          class="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 shadow-sm hover:border-slate-300 disabled:opacity-60"
          :disabled="queueStore.loading || queueStore.peekLoading"
          @click="refresh"
        >
          <RefreshCcw class="h-4 w-4" :class="{ 'animate-spin': queueStore.loading || queueStore.peekLoading }" />
          {{ queueStore.loading || queueStore.peekLoading ? 'Refreshing…' : 'Refresh' }}
        </button>
        <button
          class="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 shadow-sm hover:border-slate-300"
          :disabled="!queueStore.status.enabled"
          @click="resetStats"
        >
          <ListChecks class="h-4 w-4" />
          Reset stats
        </button>
        <button
          v-if="queueStore.status.enabled && queueStore.status.paused"
          class="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-emerald-500"
          @click="resumeQueue"
        >
          <Play class="h-4 w-4" />
          Resume
        </button>
        <button
          v-else
          class="inline-flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-700 shadow-sm hover:border-amber-300"
          :disabled="!queueStore.status.enabled"
          @click="pauseQueue"
        >
          <Pause class="h-4 w-4" />
          Pause
        </button>
        <button
          class="inline-flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm font-semibold text-rose-700 shadow-sm hover:border-rose-300"
          :disabled="!queueStore.status.enabled"
          @click="clearQueue"
        >
          <Trash2 class="h-4 w-4" />
          Clear queue
        </button>
      </div>
    </div>

    <section class="mt-6 grid gap-4 md:grid-cols-5">
      <div class="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div class="text-xs font-semibold uppercase tracking-wide text-slate-400">Status</div>
        <div class="mt-2 text-lg font-semibold text-slate-900">
          {{ queueStore.status.enabled ? 'Enabled' : 'Disabled' }}
        </div>
        <div class="mt-1 text-xs text-slate-500">
          {{ queueStore.status.paused ? 'Paused' : 'Running' }}
        </div>
      </div>
      <div class="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div class="text-xs font-semibold uppercase tracking-wide text-slate-400">Length</div>
        <div class="mt-2 text-lg font-semibold text-slate-900">{{ queueStore.status.length ?? 'n/a' }}</div>
        <div class="mt-1 text-xs text-slate-500">Items waiting</div>
      </div>
      <div class="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div class="text-xs font-semibold uppercase tracking-wide text-slate-400">Total</div>
        <div class="mt-2 text-lg font-semibold text-slate-900">{{ queueStore.status.total ?? 0 }}</div>
        <div class="mt-1 text-xs text-slate-500">Enqueued today</div>
      </div>
      <div class="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div class="text-xs font-semibold uppercase tracking-wide text-slate-400">In progress</div>
        <div class="mt-2 text-lg font-semibold text-slate-900">{{ queueStore.status.in_progress ?? 0 }}</div>
        <div class="mt-1 text-xs text-slate-500">Processing now</div>
      </div>
      <div class="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div class="text-xs font-semibold uppercase tracking-wide text-slate-400">Done</div>
        <div class="mt-2 text-lg font-semibold text-slate-900">{{ queueStore.status.done ?? 0 }}</div>
        <div class="mt-1 text-xs text-slate-500">Completed</div>
      </div>
    </section>

    <section class="mt-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <div class="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h3 class="text-lg font-semibold text-slate-900">Upcoming items</h3>
          <p class="text-sm text-slate-500">Drag order with the arrows or remove individual tasks.</p>
        </div>
        <div class="flex flex-wrap items-end gap-3">
          <label class="flex flex-col text-xs font-medium text-slate-600">
            Limit
            <input
              type="number"
              min="1"
              max="200"
              v-model.number="queueStore.peekLimit"
              class="mt-1 h-9 w-24 rounded-lg border border-slate-200 bg-slate-50 px-2 text-sm text-slate-900"
            />
          </label>
          <button
            class="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 shadow-sm hover:border-slate-300 disabled:opacity-60"
            :disabled="!queueStore.status.enabled || queueStore.peekLoading"
            @click="loadPeek"
          >
            <RefreshCcw class="h-4 w-4" :class="{ 'animate-spin': queueStore.peekLoading }" />
            {{ queueStore.peekLoading ? 'Loading…' : 'Load' }}
          </button>
        </div>
      </div>

      <div v-if="queueStore.error" class="mt-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
        {{ queueStore.error }}
      </div>
      <div v-else-if="queueStore.peekItems.length === 0" class="mt-4 text-sm text-slate-500">
        {{ queueStore.peekLoading ? 'Loading queue…' : 'No items in the queue.' }}
      </div>
      <div v-else class="mt-4 space-y-3">
        <div
          v-for="(item, index) in queueStore.peekItems"
          :key="index"
          class="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3"
        >
          <div class="flex min-w-[220px] flex-1 flex-col gap-1">
            <div class="text-sm font-semibold text-slate-900">
              {{ itemTitle(item) }}
            </div>
            <small class="text-xs text-slate-500">
              {{ itemDescription(item) }}
            </small>
          </div>
          <div class="flex items-center gap-2">
            <button
              class="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-500 hover:border-slate-300 hover:text-slate-700"
              :disabled="index === 0"
              @click="moveTop(index)"
              title="Move to top"
            >
              <ArrowUpToLine class="h-4 w-4" />
            </button>
            <button
              class="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-500 hover:border-slate-300 hover:text-slate-700"
              :disabled="index === 0"
              @click="moveItem(index, index - 1)"
              title="Move up"
            >
              <ArrowUp class="h-4 w-4" />
            </button>
            <button
              class="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-500 hover:border-slate-300 hover:text-slate-700"
              :disabled="index === queueStore.peekItems.length - 1"
              @click="moveItem(index, index + 1)"
              title="Move down"
            >
              <ArrowDown class="h-4 w-4" />
            </button>
            <button
              class="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-500 hover:border-slate-300 hover:text-slate-700"
              :disabled="index === queueStore.peekItems.length - 1"
              @click="moveBottom(index)"
              title="Move to bottom"
            >
              <ArrowDownToLine class="h-4 w-4" />
            </button>
            <button
              class="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-rose-200 bg-rose-50 text-rose-600 hover:border-rose-300 hover:text-rose-700"
              @click="removeItem(index)"
              title="Remove"
            >
              <X class="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue';
import { useQueueStore } from '../stores/queueStore';
import { ArrowDown, ArrowDownToLine, ArrowUp, ArrowUpToLine, ListChecks, Pause, Play, RefreshCcw, Trash2, X } from 'lucide-vue-next';

const queueStore = useQueueStore();

const TASK_MAP: Record<string, { label: string; description: string }> = {
  sync: { label: 'Sync document', description: 'Fetch latest metadata from Paperless.' },
  vision_ocr: { label: 'Vision OCR', description: 'Run OCR on the document pages.' },
  embeddings_paperless: { label: 'Baseline embeddings', description: 'Embed text from Paperless OCR.' },
  embeddings_vision: { label: 'Vision embeddings', description: 'Embed text from Vision OCR pages.' },
  suggestions_paperless: { label: 'AI suggestions (baseline)', description: 'Generate metadata suggestions from OCR.' },
  suggestions_vision: { label: 'AI suggestions (vision)', description: 'Generate metadata suggestions from vision OCR.' },
  suggest_field: { label: 'Field variants', description: 'Suggest alternative values for a field.' },
  full: { label: 'Full pipeline', description: 'Sync, OCR, embeddings, and suggestions.' },
};

const itemTitle = (item: { doc_id?: number; task?: string; raw?: string }) => {
  if (item.doc_id) {
    const key = item.task || 'full';
    const label = TASK_MAP[key]?.label || key;
    return `Doc ${item.doc_id} · ${label}`;
  }
  return item.raw || 'Unknown item';
};

const itemDescription = (item: { doc_id?: number; task?: string; raw?: string }) => {
  const key = item.task || 'full';
  if (item.doc_id && TASK_MAP[key]) return TASK_MAP[key].description;
  return item.raw ? 'Custom queue payload' : 'Unknown queue item';
};

const refresh = async () => {
  await queueStore.refreshStatus();
  await queueStore.loadPeek();
};

const loadPeek = async () => {
  await queueStore.loadPeek();
};

const clearQueue = async () => {
  await queueStore.clear();
};

const resetStats = async () => {
  await queueStore.resetStats();
};

const pauseQueue = async () => {
  await queueStore.pause();
};

const resumeQueue = async () => {
  await queueStore.resume();
};

const moveItem = async (fromIndex: number, toIndex: number) => {
  await queueStore.move(fromIndex, toIndex);
};

const moveTop = async (index: number) => {
  await queueStore.moveTop(index);
};

const moveBottom = async (index: number) => {
  await queueStore.moveBottom(index);
};

const removeItem = async (index: number) => {
  await queueStore.remove(index);
};

onMounted(async () => {
  await refresh();
  poller = window.setInterval(refresh, 30000);
});

let poller: number | null = null;
onUnmounted(() => {
  if (poller) window.clearInterval(poller);
});
</script>
