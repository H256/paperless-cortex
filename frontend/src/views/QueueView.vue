<template>
  <section>
    <div class="flex flex-wrap items-center justify-between gap-4">
      <div>
        <h2 class="text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">
          Queue Manager
        </h2>
        <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Control processing order and check what is coming next.
        </p>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <button
          class="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 shadow-sm hover:border-slate-300 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
          :disabled="queueStore.loading || queueStore.peekLoading"
          @click="refresh"
        >
          <RefreshCcw
            class="h-4 w-4"
            :class="{ 'animate-spin': queueStore.loading || queueStore.peekLoading }"
          />
          {{ queueStore.loading || queueStore.peekLoading ? 'Refreshing...' : 'Refresh' }}
        </button>
        <button
          class="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 shadow-sm hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
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
          class="inline-flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-700 shadow-sm hover:border-amber-300 dark:border-amber-900/50 dark:bg-amber-950/40 dark:text-amber-200"
          :disabled="!queueStore.status.enabled"
          @click="pauseQueue"
        >
          <Pause class="h-4 w-4" />
          Pause
        </button>
        <button
          class="inline-flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm font-semibold text-rose-700 shadow-sm hover:border-rose-300 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-200"
          :disabled="!queueStore.status.enabled"
          @click="clearQueue"
        >
          <Trash2 class="h-4 w-4" />
          Clear queue
        </button>
      </div>
    </div>

    <section class="mt-6 grid gap-4 md:grid-cols-5">
      <div
        class="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900"
      >
        <div
          class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500"
        >
          Status
        </div>
        <div class="mt-2 text-lg font-semibold text-slate-900 dark:text-slate-100">
          {{ queueStore.status.enabled ? 'Enabled' : 'Disabled' }}
        </div>
        <div class="mt-1 text-xs text-slate-500 dark:text-slate-400">
          {{ queueStore.status.paused ? 'Paused' : 'Running' }}
        </div>
      </div>
      <div
        class="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900"
      >
        <div
          class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500"
        >
          Length
        </div>
        <div class="mt-2 text-lg font-semibold text-slate-900 dark:text-slate-100">
          {{ queueStore.status.length ?? 'n/a' }}
        </div>
        <div class="mt-1 text-xs text-slate-500 dark:text-slate-400">Items waiting</div>
      </div>
      <div
        class="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900"
      >
        <div
          class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500"
        >
          Total
        </div>
        <div class="mt-2 text-lg font-semibold text-slate-900 dark:text-slate-100">
          {{ queueStore.status.total ?? 0 }}
        </div>
        <div class="mt-1 text-xs text-slate-500 dark:text-slate-400">Enqueued today</div>
      </div>
      <div
        class="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900"
      >
        <div
          class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500"
        >
          In progress
        </div>
        <div class="mt-2 text-lg font-semibold text-slate-900 dark:text-slate-100">
          {{ queueStore.status.in_progress ?? 0 }}
        </div>
        <div class="mt-1 text-xs text-slate-500 dark:text-slate-400">Processing now</div>
      </div>
      <div
        class="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900"
      >
        <div
          class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500"
        >
          Done
        </div>
        <div class="mt-2 text-lg font-semibold text-slate-900 dark:text-slate-100">
          {{ queueStore.status.done ?? 0 }}
        </div>
        <div class="mt-1 text-xs text-slate-500 dark:text-slate-400">Completed</div>
      </div>
    </section>

    <section
      class="mt-6 rounded-xl border border-indigo-200 bg-indigo-50/60 p-4 shadow-sm dark:border-indigo-900/40 dark:bg-indigo-950/20"
    >
      <div class="text-xs font-semibold uppercase tracking-wide text-indigo-500 dark:text-indigo-300">
        Running now
      </div>
      <div
        v-if="queueStore.running.task?.doc_id"
        class="mt-2 text-sm font-semibold text-slate-900 dark:text-slate-100"
      >
        {{ itemTitle(queueStore.running.task) }}
      </div>
      <div
        v-if="queueStore.running.task?.doc_id"
        class="mt-1 text-xs text-slate-500 dark:text-slate-400"
      >
        {{ itemDescription(queueStore.running.task) }}
      </div>
      <div
        v-if="queueStore.running.started_at"
        class="mt-1 text-xs text-slate-500 dark:text-slate-400"
      >
        Started: {{ formatStartedAt(queueStore.running.started_at) }} ({{ formatRuntime(queueStore.running.started_at) }})
      </div>
      <div
        v-else
        class="mt-2 text-sm text-slate-500 dark:text-slate-400"
      >
        No task currently running.
      </div>
    </section>

    <section
      class="mt-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900"
    >
      <div class="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h3 class="text-lg font-semibold text-slate-900 dark:text-slate-100">Upcoming items</h3>
          <p class="text-sm text-slate-500 dark:text-slate-400">
            Drag order with the arrows or remove individual tasks.
          </p>
        </div>
        <div class="flex flex-wrap items-end gap-3">
          <label class="flex flex-col text-xs font-medium text-slate-600 dark:text-slate-300">
            Doc ID
            <input
              type="text"
              v-model="docIdFilter"
              placeholder="Filter"
              class="mt-1 h-9 w-32 rounded-lg border border-slate-200 bg-slate-50 px-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            />
          </label>
          <label class="flex flex-col text-xs font-medium text-slate-600 dark:text-slate-300">
            Limit
            <input
              type="number"
              min="1"
              max="200"
              v-model.number="queueStore.peekLimit"
              class="mt-1 h-9 w-24 rounded-lg border border-slate-200 bg-slate-50 px-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            />
          </label>
          <button
            class="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 shadow-sm hover:border-slate-300 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
            :disabled="!queueStore.status.enabled || queueStore.peekLoading"
            @click="loadPeek"
          >
            <RefreshCcw class="h-4 w-4" :class="{ 'animate-spin': queueStore.peekLoading }" />
            {{ queueStore.peekLoading ? 'Loading...' : 'Load' }}
          </button>
        </div>
      </div>

      <div
        v-if="queueStore.error"
        class="mt-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-200"
      >
        {{ queueStore.error }}
      </div>
      <div
        v-else-if="queueStore.peekItems.length === 0"
        class="mt-4 text-sm text-slate-500 dark:text-slate-400"
      >
        {{ queueStore.peekLoading ? 'Loading queue...' : 'No items in the queue.' }}
      </div>
      <div
        v-else-if="filteredItems.length === 0"
        class="mt-4 text-sm text-slate-500 dark:text-slate-400"
      >
        No items match the Doc ID filter.
      </div>
      <div v-else class="mt-4 space-y-3">
        <div
          v-for="entry in filteredItems"
          :key="entry.index"
          class="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 dark:border-slate-800 dark:bg-slate-800"
        >
          <div class="flex min-w-[220px] flex-1 flex-col gap-1">
            <div class="text-sm font-semibold text-slate-900 dark:text-slate-100">
              {{ itemTitle(entry.item) }}
            </div>
            <small class="text-xs text-slate-500 dark:text-slate-400">
              {{ itemDescription(entry.item) }}
            </small>
          </div>
          <div class="flex items-center gap-2">
            <button
              class="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-500 hover:border-slate-300 hover:text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-slate-500"
              :disabled="entry.index === 0"
              @click="moveTop(entry.index)"
              title="Move to top"
            >
              <ArrowUpToLine class="h-4 w-4" />
            </button>
            <button
              class="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-500 hover:border-slate-300 hover:text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-slate-500"
              :disabled="entry.index === 0"
              @click="moveItem(entry.index, entry.index - 1)"
              title="Move up"
            >
              <ArrowUp class="h-4 w-4" />
            </button>
            <button
              class="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-500 hover:border-slate-300 hover:text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-slate-500"
              :disabled="entry.index === queueStore.peekItems.length - 1"
              @click="moveItem(entry.index, entry.index + 1)"
              title="Move down"
            >
              <ArrowDown class="h-4 w-4" />
            </button>
            <button
              class="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-500 hover:border-slate-300 hover:text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-slate-500"
              :disabled="entry.index === queueStore.peekItems.length - 1"
              @click="moveBottom(entry.index)"
              title="Move to bottom"
            >
              <ArrowDownToLine class="h-4 w-4" />
            </button>
            <button
              class="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-rose-200 bg-rose-50 text-rose-600 hover:border-rose-300 hover:text-rose-700 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-200"
              @click="removeItem(entry.index)"
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
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useQueueStore } from '../stores/queueStore'
import {
  ArrowDown,
  ArrowDownToLine,
  ArrowUp,
  ArrowUpToLine,
  ListChecks,
  Pause,
  Play,
  RefreshCcw,
  Trash2,
  X,
} from 'lucide-vue-next'

const queueStore = useQueueStore()
const docIdFilter = ref('')

const filteredItems = computed(() => {
  const needle = docIdFilter.value.trim()
  const items = queueStore.peekItems.map((item, index) => ({ item, index }))
  if (!needle) return items
  return items.filter(({ item }) => item.doc_id && String(item.doc_id).includes(needle))
})

const TASK_MAP: Record<string, { label: string; description: string }> = {
  sync: { label: 'Sync document', description: 'Fetch latest metadata from Paperless.' },
  vision_ocr: { label: 'Vision OCR', description: 'Run OCR on the document pages.' },
  embeddings_paperless: {
    label: 'Baseline embeddings',
    description: 'Embed text from Paperless OCR.',
  },
  embeddings_vision: {
    label: 'Vision embeddings',
    description: 'Embed text from Vision OCR pages.',
  },
  suggestions_paperless: {
    label: 'AI suggestions (baseline)',
    description: 'Generate metadata suggestions from OCR.',
  },
  suggestions_vision: {
    label: 'AI suggestions (vision)',
    description: 'Generate metadata suggestions from vision OCR.',
  },
  suggest_field: {
    label: 'Field variants',
    description: 'Suggest alternative values for a field.',
  },
  full: { label: 'Full pipeline', description: 'Sync, OCR, embeddings, and suggestions.' },
}

const itemTitle = (item: { doc_id?: number; task?: string; raw?: string }) => {
  if (item.doc_id) {
    const key = item.task || 'full'
    const label = TASK_MAP[key]?.label || key
    return `Doc ${item.doc_id} - ${label}`
  }
  return item.raw || 'Unknown item'
}

const itemDescription = (item: { doc_id?: number; task?: string; raw?: string }) => {
  const key = item.task || 'full'
  if (item.doc_id && TASK_MAP[key]) return TASK_MAP[key].description
  return item.raw ? 'Custom queue payload' : 'Unknown queue item'
}

const refresh = async () => {
  await queueStore.refreshStatus()
  await queueStore.loadPeek()
}

const loadPeek = async () => {
  await queueStore.loadPeek()
}

const clearQueue = async () => {
  await queueStore.clear()
}

const resetStats = async () => {
  await queueStore.resetStats()
}

const pauseQueue = async () => {
  await queueStore.pause()
}

const resumeQueue = async () => {
  await queueStore.resume()
}

const moveItem = async (fromIndex: number, toIndex: number) => {
  await queueStore.move(fromIndex, toIndex)
}

const moveTop = async (index: number) => {
  await queueStore.moveTop(index)
}

const moveBottom = async (index: number) => {
  await queueStore.moveBottom(index)
}

const removeItem = async (index: number) => {
  await queueStore.remove(index)
}

const formatStartedAt = (unixTs: number) => new Date(unixTs * 1000).toLocaleString()

const formatRuntime = (unixTs: number) => {
  const seconds = Math.max(0, Math.floor(Date.now() / 1000) - unixTs)
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  if (mins <= 0) return `${secs}s`
  if (mins < 60) return `${mins}m ${secs}s`
  const hours = Math.floor(mins / 60)
  const remMins = mins % 60
  return `${hours}h ${remMins}m`
}

onMounted(async () => {
  await refresh()
  poller = window.setInterval(refresh, 30000)
})

let poller: number | null = null
onUnmounted(() => {
  if (poller) window.clearInterval(poller)
})
</script>
