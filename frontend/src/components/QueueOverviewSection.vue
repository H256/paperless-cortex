<template>
  <div>
    <div class="flex flex-wrap items-center justify-between gap-4">
      <div>
        <h2 class="text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">
          Queue Manager
        </h2>
        <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Control processing order and check what is coming next.
        </p>
        <p class="mt-1 text-xs text-slate-500 dark:text-slate-400">
          {{ shouldAutoRefreshQueue ? 'Auto-refresh active (5s).' : 'Auto-refresh idle.' }}
          Last update: {{ formatRelativeTime(lastRefreshedAt) }}
          <span class="opacity-70">({{ formatDateTime(lastRefreshedAt) || '-' }})</span>
        </p>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <button
          class="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 shadow-sm hover:border-slate-300 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
          :disabled="loading || peekLoading || busy"
          @click="$emit('refresh')"
        >
          <RefreshCcw
            class="h-4 w-4"
            :class="{ 'animate-spin': loading || peekLoading || busy }"
          />
          {{ loading || peekLoading || busy ? 'Refreshing...' : 'Refresh' }}
        </button>
        <button
          class="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 shadow-sm hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
          :disabled="!status.enabled || busy"
          @click="$emit('reset-stats')"
        >
          <ListChecks class="h-4 w-4" />
          Reset stats
        </button>
        <button
          v-if="status.enabled && status.paused"
          class="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-emerald-500"
          @click="$emit('resume-queue')"
        >
          <Play class="h-4 w-4" />
          Resume
        </button>
        <button
          v-else
          class="inline-flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-700 shadow-sm hover:border-amber-300 dark:border-amber-900/50 dark:bg-amber-950/40 dark:text-amber-200"
          :disabled="!status.enabled || busy"
          @click="$emit('pause-queue')"
        >
          <Pause class="h-4 w-4" />
          Pause
        </button>
        <button
          class="inline-flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm font-semibold text-rose-700 shadow-sm hover:border-rose-300 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-200"
          :disabled="!status.enabled || busy"
          @click="$emit('clear-queue')"
        >
          <Trash2 class="h-4 w-4" />
          Clear queue
        </button>
      </div>
    </div>

    <section class="mt-6 grid gap-4 md:grid-cols-5">
      <div
        v-for="card in statusCards"
        :key="card.label"
        class="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900"
      >
        <div
          class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500"
        >
          {{ card.label }}
        </div>
        <div class="mt-2 text-lg font-semibold text-slate-900 dark:text-slate-100">
          {{ card.value }}
        </div>
        <div class="mt-1 text-xs text-slate-500 dark:text-slate-400">{{ card.caption }}</div>
      </div>
    </section>

    <section
      class="mt-6 rounded-xl border border-indigo-200 bg-indigo-50/60 p-4 shadow-sm dark:border-indigo-900/40 dark:bg-indigo-950/20"
    >
      <div class="text-xs font-semibold uppercase tracking-wide text-indigo-500 dark:text-indigo-300">
        Running now
      </div>
      <div
        v-if="running.task?.doc_id"
        class="mt-2 text-sm font-semibold text-slate-900 dark:text-slate-100"
      >
        {{ itemTitle(running.task) }}
      </div>
      <div
        v-if="running.task?.doc_id"
        class="mt-1 text-xs text-slate-500 dark:text-slate-400"
      >
        {{ itemDescription(running.task) }}
      </div>
      <div
        v-if="running.started_at"
        class="mt-1 text-xs text-slate-500 dark:text-slate-400"
      >
        Started: {{ formatStartedAt(running.started_at) }} ({{ formatRuntime(running.started_at) }})
      </div>
      <div
        v-else
        class="mt-2 text-sm text-slate-500 dark:text-slate-400"
      >
        No task currently running.
      </div>
    </section>

    <section
      class="mt-6 rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900"
    >
      <div class="flex items-center justify-between gap-3">
        <div>
          <h3 class="text-sm font-semibold text-slate-900 dark:text-slate-100">Recent task runs</h3>
          <p class="text-xs text-slate-500 dark:text-slate-400">
            Compact timeline for quick worker triage.
          </p>
        </div>
        <button
          class="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs font-semibold text-slate-700 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
          :disabled="taskRunsLoading"
          @click="$emit('reload-task-runs')"
        >
          <RefreshCcw class="h-3.5 w-3.5" :class="{ 'animate-spin': taskRunsLoading }" />
          {{ taskRunsLoading ? 'Loading...' : 'Reload' }}
        </button>
      </div>
      <div
        v-if="recentTaskRuns.length === 0"
        class="mt-3 text-xs text-slate-500 dark:text-slate-400"
      >
        {{ taskRunsLoading ? 'Loading runs...' : 'No recent runs for current filter.' }}
      </div>
      <div v-else class="mt-3 space-y-2">
        <div
          v-for="run in recentTaskRuns"
          :key="`timeline-${run.id}`"
          class="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs dark:border-slate-800 dark:bg-slate-800"
        >
          <div class="min-w-0 flex-1">
            <div class="truncate font-semibold text-slate-800 dark:text-slate-100">
              #{{ run.id }} - {{ run.task }} <span v-if="run.doc_id">- Doc {{ run.doc_id }}</span>
            </div>
            <div class="mt-0.5 text-slate-500 dark:text-slate-400">
              {{ formatRelativeTime(run.started_at || run.created_at) }}
              <span class="opacity-70">({{ formatDateTime(run.started_at || run.created_at) || '-' }})</span>
            </div>
          </div>
          <div class="flex shrink-0 items-center gap-1.5">
            <span
              class="rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
              :class="run.status === 'failed'
                ? 'border border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900/50 dark:bg-rose-950/30 dark:text-rose-200'
                : 'border border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/50 dark:bg-emerald-950/30 dark:text-emerald-200'"
            >
              {{ run.status }}
            </span>
            <span
              v-if="run.error_type"
              class="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[10px] font-semibold text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
              :title="run.error_message || run.error_type"
            >
              {{ run.error_type }}
            </span>
            <span
              v-if="run.duration_ms != null"
              class="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[10px] font-semibold text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
            >
              {{ run.duration_ms }} ms
            </span>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ListChecks, Pause, Play, RefreshCcw, Trash2 } from 'lucide-vue-next'
import type { QueueRunningStatus, QueueStatus, QueueTaskRun } from '../services/queue'
import { formatDateTime, formatRelativeTime } from '../utils/dateTime'
import {
  queueFormatRuntime as formatRuntime,
  queueFormatStartedAt as formatStartedAt,
  queueItemDescription as itemDescription,
  queueItemTitle as itemTitle,
} from '../utils/queueView'

const props = defineProps<{
  status: QueueStatus
  running: QueueRunningStatus
  recentTaskRuns: QueueTaskRun[]
  taskRunsLoading: boolean
  loading: boolean
  peekLoading: boolean
  busy: boolean
  shouldAutoRefreshQueue: boolean
  lastRefreshedAt: string | null
}>()

defineEmits<{
  (e: 'refresh'): void
  (e: 'reset-stats'): void
  (e: 'resume-queue'): void
  (e: 'pause-queue'): void
  (e: 'clear-queue'): void
  (e: 'reload-task-runs'): void
}>()

const statusCards = computed(() => [
  {
    label: 'Status',
    value: props.status.enabled ? 'Enabled' : 'Disabled',
    caption: props.status.paused ? 'Paused' : 'Running',
  },
  {
    label: 'Length',
    value: props.status.length ?? 'n/a',
    caption: 'Items waiting',
  },
  {
    label: 'Total',
    value: props.status.total ?? 0,
    caption: 'Enqueued today',
  },
  {
    label: 'In progress',
    value: props.status.in_progress ?? 0,
    caption: 'Processing now',
  },
  {
    label: 'Done',
    value: props.status.done ?? 0,
    caption: 'Completed',
  },
])
</script>
