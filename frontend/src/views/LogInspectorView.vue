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
        Showing {{ taskRuns.length }} of {{ taskRunsCount }} run(s)
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
    </section>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useTaskRunInspector } from '../composables/useTaskRunInspector'
import { useToastStore } from '../stores/toastStore'
import { formatDateTime, formatRelativeTime } from '../utils/dateTime'
import { formatCheckpointLabel } from '../utils/taskRunCheckpoint'

const router = useRouter()
const toastStore = useToastStore()
const presetName = ref('')
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
} = useTaskRunInspector()

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
</script>
