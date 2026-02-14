<template>
  <section>
    <div class="flex flex-wrap items-center justify-between gap-4">
      <div>
        <h2 class="text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">
          Log Inspector
        </h2>
        <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Explore worker task runs with advanced filters and reusable presets.
        </p>
      </div>
      <div class="flex items-center gap-2">
        <button
          class="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
          :disabled="loading"
          @click="refresh"
        >
          {{ loading ? 'Loading...' : 'Reload' }}
        </button>
      </div>
    </div>

    <section class="mt-6 rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <details class="rounded-lg border border-slate-200 p-3 dark:border-slate-700">
        <summary class="cursor-pointer text-xs font-semibold text-slate-600 dark:text-slate-300">
          Error type reference
        </summary>
        <div v-if="errorTypes.length === 0" class="mt-2 text-xs text-slate-500 dark:text-slate-400">
          No error catalog available.
        </div>
        <div v-else class="mt-2 overflow-x-auto">
          <table class="min-w-full text-xs">
            <thead class="text-left text-slate-500 dark:text-slate-400">
              <tr>
                <th class="px-2 py-1">Code</th>
                <th class="px-2 py-1">Retryable</th>
                <th class="px-2 py-1">Category</th>
                <th class="px-2 py-1">Description</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="entry in errorTypes"
                :key="entry.code"
                class="border-t border-slate-100 dark:border-slate-800"
              >
                <td class="px-2 py-1.5 font-mono">{{ entry.code }}</td>
                <td class="px-2 py-1.5">{{ entry.retryable ? 'yes' : 'no' }}</td>
                <td class="px-2 py-1.5">{{ entry.category }}</td>
                <td class="px-2 py-1.5">{{ entry.description }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </details>

      <div class="grid gap-3 md:grid-cols-4">
        <label class="flex flex-col text-xs font-medium text-slate-600 dark:text-slate-300">
          Doc ID
          <input v-model="filters.docId.value" class="mt-1 h-9 rounded-lg border border-slate-200 bg-slate-50 px-2 text-sm dark:border-slate-700 dark:bg-slate-900" />
        </label>
        <label class="flex flex-col text-xs font-medium text-slate-600 dark:text-slate-300">
          Task
          <input v-model="filters.task.value" class="mt-1 h-9 rounded-lg border border-slate-200 bg-slate-50 px-2 text-sm dark:border-slate-700 dark:bg-slate-900" />
        </label>
        <label class="flex flex-col text-xs font-medium text-slate-600 dark:text-slate-300">
          Status
          <select v-model="filters.status.value" class="mt-1 h-9 rounded-lg border border-slate-200 bg-slate-50 px-2 text-sm dark:border-slate-700 dark:bg-slate-900">
            <option value="">all</option>
            <option value="running">running</option>
            <option value="retrying">retrying</option>
            <option value="failed">failed</option>
            <option value="done">done</option>
          </select>
        </label>
        <label class="flex flex-col text-xs font-medium text-slate-600 dark:text-slate-300">
          Error type
          <input v-model="filters.errorType.value" class="mt-1 h-9 rounded-lg border border-slate-200 bg-slate-50 px-2 text-sm dark:border-slate-700 dark:bg-slate-900" />
        </label>
      </div>
      <div class="mt-3 grid gap-3 md:grid-cols-[1fr_auto_auto_auto]">
        <label class="flex flex-col text-xs font-medium text-slate-600 dark:text-slate-300">
          Full-text search
          <input v-model="filters.query.value" class="mt-1 h-9 rounded-lg border border-slate-200 bg-slate-50 px-2 text-sm dark:border-slate-700 dark:bg-slate-900" placeholder="task/source/status/error..." />
        </label>
        <label class="flex flex-col text-xs font-medium text-slate-600 dark:text-slate-300">
          Limit
          <input v-model.number="filters.limit.value" type="number" min="1" max="500" class="mt-1 h-9 w-24 rounded-lg border border-slate-200 bg-slate-50 px-2 text-sm dark:border-slate-700 dark:bg-slate-900" />
        </label>
        <label class="inline-flex items-center gap-2 self-end text-xs font-medium text-slate-600 dark:text-slate-300">
          <input v-model="filters.autoRefresh.value" type="checkbox" />
          Auto refresh
        </label>
        <button
          class="self-end rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
          @click="clearFilters"
        >
          Clear
        </button>
      </div>
      <div class="mt-3 flex flex-wrap items-center gap-2">
        <input
          v-model="presetName"
          placeholder="Preset name"
          class="h-8 w-44 rounded-md border border-slate-200 bg-slate-50 px-2 text-xs dark:border-slate-700 dark:bg-slate-900"
        />
        <button
          class="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
          @click="saveCurrentPreset"
        >
          Save preset
        </button>
        <button
          class="rounded-md border border-indigo-200 bg-indigo-50 px-2 py-1 text-xs font-semibold text-indigo-700 hover:border-indigo-300 dark:border-indigo-900/50 dark:bg-indigo-950/30 dark:text-indigo-200"
          @click="applyQuickFilter('failed')"
        >
          Only failed
        </button>
        <button
          class="rounded-md border border-indigo-200 bg-indigo-50 px-2 py-1 text-xs font-semibold text-indigo-700 hover:border-indigo-300 dark:border-indigo-900/50 dark:bg-indigo-950/30 dark:text-indigo-200"
          @click="applyQuickFilter('retrying')"
        >
          Retrying now
        </button>
        <button
          class="rounded-md border border-indigo-200 bg-indigo-50 px-2 py-1 text-xs font-semibold text-indigo-700 hover:border-indigo-300 dark:border-indigo-900/50 dark:bg-indigo-950/30 dark:text-indigo-200"
          @click="applyQuickFilter('embedding_overflow')"
        >
          Embedding overflows
        </button>
        <button
          class="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-700 hover:border-emerald-300 dark:border-emerald-900/50 dark:bg-emerald-950/30 dark:text-emerald-200"
          :disabled="taskRuns.length === 0"
          @click="exportJson"
        >
          Export JSON
        </button>
        <button
          class="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-700 hover:border-emerald-300 dark:border-emerald-900/50 dark:bg-emerald-950/30 dark:text-emerald-200"
          :disabled="taskRuns.length === 0"
          @click="exportCsv"
        >
          Export CSV
        </button>
        <button
          v-for="preset in presets"
          :key="preset.id"
          class="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2 py-1 text-xs text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
        >
          <span @click="applyPreset(preset.id)" class="cursor-pointer">{{ preset.name }}</span>
          <span class="cursor-pointer text-rose-500" @click="deletePreset(preset.id)">x</span>
        </button>
      </div>
    </section>

    <section class="mt-6 rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div class="text-xs text-slate-500 dark:text-slate-400">
        Showing {{ taskRuns.length }} of {{ taskRunsCount }} run(s), offset {{ filters.offset.value }}
      </div>
      <div v-if="error" class="mt-2 text-sm text-rose-600 dark:text-rose-300">{{ error }}</div>
      <div v-else-if="taskRuns.length === 0" class="mt-2 text-sm text-slate-500 dark:text-slate-400">
        {{ loading ? 'Loading task runs...' : 'No task runs found.' }}
      </div>
      <div v-else class="mt-3 overflow-x-auto">
        <table class="min-w-full text-xs">
          <thead class="text-left text-slate-500 dark:text-slate-400">
            <tr>
              <th class="px-2 py-1">Run</th>
              <th class="px-2 py-1">Doc</th>
              <th class="px-2 py-1">Task</th>
              <th class="px-2 py-1">Status</th>
              <th class="px-2 py-1">Checkpoint</th>
              <th class="px-2 py-1">Error</th>
              <th class="px-2 py-1">Started</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="run in taskRuns" :key="run.id" class="border-t border-slate-100 dark:border-slate-800">
              <td class="px-2 py-1.5">#{{ run.id }}</td>
              <td class="px-2 py-1.5">
                <button
                  v-if="run.doc_id"
                  class="rounded-md border border-slate-200 bg-white px-1.5 py-0.5 text-[11px] font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
                  @click="openDocument(run.doc_id)"
                >
                  {{ run.doc_id }}
                </button>
                <span v-else>-</span>
              </td>
              <td class="px-2 py-1.5">{{ run.task }}</td>
              <td class="px-2 py-1.5">{{ run.status }}</td>
              <td class="px-2 py-1.5">{{ formatTaskCheckpoint(run.checkpoint) }}</td>
              <td class="px-2 py-1.5">
                <div>{{ run.error_type || '-' }}</div>
                <div v-if="run.error_message" class="text-[11px] text-slate-500 dark:text-slate-400" :title="run.error_message">
                  {{ compactMessage(run.error_message) }}
                  <button class="ml-1 text-indigo-600 dark:text-indigo-300" @click="copyError(run.error_message)">copy</button>
                </div>
              </td>
              <td class="px-2 py-1.5" :title="formatDateTime(run.started_at) || '-'">{{ formatRelativeTime(run.started_at) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="mt-3 flex items-center gap-2">
        <button
          class="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-semibold text-slate-600 hover:border-slate-300 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
          :disabled="filters.offset.value <= 0 || loading"
          @click="prevPage"
        >
          Prev
        </button>
        <button
          class="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-semibold text-slate-600 hover:border-slate-300 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
          :disabled="filters.offset.value + filters.limit.value >= taskRunsCount || loading"
          @click="nextPage"
        >
          Next
        </button>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useTaskRunInspector } from '../composables/useTaskRunInspector'
import { fetchQueueErrorTypes, type QueueErrorTypeDetail } from '../services/queue'
import { useToastStore } from '../stores/toastStore'
import { formatDateTime, formatRelativeTime } from '../utils/dateTime'
import { formatCheckpointLabel } from '../utils/taskRunCheckpoint'

const router = useRouter()
const toastStore = useToastStore()
const presetName = ref('')
const errorTypes = ref<QueueErrorTypeDetail[]>([])
const {
  filters,
  taskRuns,
  taskRunsCount,
  loading,
  error,
  refresh,
  presets,
  savePreset,
  applyPreset,
  deletePreset,
  clearFilters,
  nextPage,
  prevPage,
} = useTaskRunInspector()

const loadErrorTypes = async () => {
  try {
    const response = await fetchQueueErrorTypes()
    errorTypes.value = response.enabled ? response.items ?? [] : []
  } catch {
    errorTypes.value = []
  }
}

const formatTaskCheckpoint = (checkpoint?: Record<string, unknown> | null) =>
  formatCheckpointLabel(checkpoint, '-')

const compactMessage = (message?: string | null) => {
  if (!message) return ''
  const normalized = message.replace(/\s+/g, ' ').trim()
  if (normalized.length <= 100) return normalized
  return `${normalized.slice(0, 97)}...`
}

const openDocument = (docId: number) => {
  router.push(`/documents/${docId}`)
}

const copyError = async (message: string) => {
  try {
    await navigator.clipboard.writeText(message)
    toastStore.push('Error copied.', 'success', 'Logs', 1200)
  } catch {
    toastStore.push('Copy failed.', 'danger', 'Logs', 1800)
  }
}

const saveCurrentPreset = () => {
  if (!savePreset(presetName.value)) {
    toastStore.push('Preset name required.', 'warning', 'Logs', 1400)
    return
  }
  presetName.value = ''
  toastStore.push('Preset saved.', 'success', 'Logs', 1200)
}

const applyQuickFilter = (kind: 'failed' | 'retrying' | 'embedding_overflow') => {
  clearFilters()
  if (kind === 'failed') {
    filters.status.value = 'failed'
  } else if (kind === 'retrying') {
    filters.status.value = 'retrying'
  } else {
    filters.status.value = 'failed'
    filters.task.value = 'embeddings_vision'
    filters.query.value = 'overflow'
  }
}

const downloadBlob = (filename: string, content: string, mime: string) => {
  const blob = new Blob([content], { type: mime })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

const exportJson = () => {
  const payload = {
    filters: {
      doc_id: filters.docId.value || null,
      task: filters.task.value || null,
      status: filters.status.value || null,
      error_type: filters.errorType.value || null,
      q: filters.query.value || null,
      limit: filters.limit.value,
      offset: filters.offset.value,
    },
    count: taskRunsCount.value,
    items: taskRuns.value,
  }
  downloadBlob(
    `task-runs-${Date.now()}.json`,
    JSON.stringify(payload, null, 2),
    'application/json;charset=utf-8',
  )
}

const csvEscape = (value: unknown) => {
  const text = String(value ?? '')
  if (!/[",\n]/.test(text)) return text
  return `"${text.replace(/"/g, '""')}"`
}

const exportCsv = () => {
  const columns = [
    'id',
    'doc_id',
    'task',
    'source',
    'status',
    'attempt',
    'error_type',
    'error_message',
    'started_at',
    'finished_at',
    'duration_ms',
  ]
  const lines = [columns.join(',')]
  for (const run of taskRuns.value) {
    const row = [
      csvEscape(run.id),
      csvEscape(run.doc_id),
      csvEscape(run.task),
      csvEscape(run.source),
      csvEscape(run.status),
      csvEscape(run.attempt),
      csvEscape(run.error_type),
      csvEscape(run.error_message),
      csvEscape(run.started_at),
      csvEscape(run.finished_at),
      csvEscape(run.duration_ms),
    ]
    lines.push(row.join(','))
  }
  downloadBlob(`task-runs-${Date.now()}.csv`, lines.join('\n'), 'text/csv;charset=utf-8')
}

onMounted(() => {
  void loadErrorTypes()
})
</script>
