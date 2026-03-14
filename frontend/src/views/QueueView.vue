<template>
  <section>
    <QueueOverviewSection
      :status="status"
      :running="running"
      :recent-task-runs="recentTaskRuns"
      :task-runs-loading="taskRunsLoading"
      :loading="loading"
      :peek-loading="peekLoading"
      :busy="busy"
      :should-auto-refresh-queue="shouldAutoRefreshQueue"
      :last-refreshed-at="lastRefreshedAt"
      @refresh="refresh"
      @reset-stats="resetStats"
      @resume-queue="resumeQueue"
      @pause-queue="pauseQueue"
      @clear-queue="clearQueue"
      @reload-task-runs="loadTaskRuns"
    />

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
              v-model.number="peekLimit"
              class="mt-1 h-9 w-24 rounded-lg border border-slate-200 bg-slate-50 px-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            />
          </label>
          <button
            class="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 shadow-sm hover:border-slate-300 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
            :disabled="!status.enabled || peekLoading || busy"
            @click="loadPeek"
          >
            <RefreshCcw class="h-4 w-4" :class="{ 'animate-spin': peekLoading || busy }" />
            {{ peekLoading || busy ? 'Loading...' : 'Load' }}
          </button>
        </div>
      </div>

      <div
        v-if="error"
        class="mt-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-200"
      >
        {{ error }}
      </div>
      <div
        v-else-if="peekItems.length === 0"
        class="mt-4 text-sm text-slate-500 dark:text-slate-400"
      >
        {{ peekLoading ? 'Loading queue...' : 'No items in the queue.' }}
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
              :disabled="entry.index === peekItems.length - 1"
              @click="moveItem(entry.index, entry.index + 1)"
              title="Move down"
            >
              <ArrowDown class="h-4 w-4" />
            </button>
            <button
              class="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-500 hover:border-slate-300 hover:text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-slate-500"
              :disabled="entry.index === peekItems.length - 1"
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

    <section
      class="mt-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900"
    >
      <div class="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h3 class="text-lg font-semibold text-slate-900 dark:text-slate-100">Task run history</h3>
          <p class="text-sm text-slate-500 dark:text-slate-400">
            Inspect recent worker executions with typed errors and timing.
          </p>
        </div>
        <div class="flex flex-wrap items-end gap-3">
          <label class="flex flex-col text-xs font-medium text-slate-600 dark:text-slate-300">
            Doc ID
            <input
              type="text"
              v-model="taskRunsDocId"
              placeholder="e.g. 1756"
              class="mt-1 h-9 w-28 rounded-lg border border-slate-200 bg-slate-50 px-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            />
          </label>
          <label class="flex flex-col text-xs font-medium text-slate-600 dark:text-slate-300">
            Task
            <input
              type="text"
              v-model="taskRunsTask"
              placeholder="embeddings_vision"
              class="mt-1 h-9 w-44 rounded-lg border border-slate-200 bg-slate-50 px-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            />
          </label>
          <label class="flex flex-col text-xs font-medium text-slate-600 dark:text-slate-300">
            Status
            <select
              v-model="taskRunsStatus"
              class="mt-1 h-9 w-28 rounded-lg border border-slate-200 bg-slate-50 px-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            >
              <option value="">all</option>
              <option value="completed">completed</option>
              <option value="failed">failed</option>
              <option value="running">running</option>
            </select>
          </label>
          <label class="flex flex-col text-xs font-medium text-slate-600 dark:text-slate-300">
            Error type
            <input
              type="text"
              v-model="taskRunsErrorType"
              placeholder="EMBED_CONTEXT_OVERFLOW"
              class="mt-1 h-9 w-52 rounded-lg border border-slate-200 bg-slate-50 px-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            />
          </label>
          <label class="flex flex-col text-xs font-medium text-slate-600 dark:text-slate-300">
            Search
            <input
              type="text"
              v-model="taskRunsQuery"
              placeholder="message/task/source contains..."
              class="mt-1 h-9 w-64 rounded-lg border border-slate-200 bg-slate-50 px-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            />
          </label>
          <label class="flex flex-col text-xs font-medium text-slate-600 dark:text-slate-300">
            Limit
            <input
              type="number"
              min="1"
              max="500"
              v-model.number="taskRunsLimit"
              class="mt-1 h-9 w-20 rounded-lg border border-slate-200 bg-slate-50 px-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            />
          </label>
          <button
            class="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 shadow-sm hover:border-slate-300 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
            :disabled="taskRunsLoading"
            @click="loadTaskRuns"
          >
            <RefreshCcw class="h-4 w-4" :class="{ 'animate-spin': taskRunsLoading }" />
            {{ taskRunsLoading ? 'Loading...' : 'Reload' }}
          </button>
          <button
            class="inline-flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-700 shadow-sm hover:border-amber-300 disabled:opacity-60 dark:border-amber-900/50 dark:bg-amber-950/40 dark:text-amber-200"
            :disabled="taskRunsLoading || failedTaskRuns.length === 0 || busy"
            @click="retryFailedTaskRuns"
          >
            Retry failed (filtered)
          </button>
        </div>
      </div>

      <div v-if="taskRuns.length === 0" class="mt-4 text-sm text-slate-500 dark:text-slate-400">
        {{ taskRunsLoading ? 'Loading task runs...' : 'No task runs found for current filters.' }}
      </div>
      <div v-else class="mt-4 overflow-x-auto">
        <table class="min-w-full text-xs">
          <thead class="text-left text-slate-500 dark:text-slate-400">
            <tr>
              <th class="px-2 py-1">Run</th>
              <th class="px-2 py-1">Doc</th>
              <th class="px-2 py-1">Task</th>
              <th class="px-2 py-1">Status</th>
              <th class="px-2 py-1">Error Type</th>
              <th class="px-2 py-1">Message</th>
              <th class="px-2 py-1">Checkpoint</th>
              <th class="px-2 py-1">Duration</th>
              <th class="px-2 py-1">Started</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="run in taskRuns"
              :key="run.id"
              class="border-t border-slate-100 dark:border-slate-800"
            >
              <td class="px-2 py-2 font-semibold text-slate-700 dark:text-slate-200">#{{ run.id }}</td>
              <td class="px-2 py-2">
                <button
                  v-if="run.doc_id"
                  class="rounded-md border border-slate-200 bg-white px-1.5 py-0.5 text-[11px] font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
                  @click="openDocument(run.doc_id)"
                >
                  {{ run.doc_id }}
                </button>
                <span v-else>-</span>
              </td>
              <td class="px-2 py-2">{{ run.task }}</td>
              <td
                class="px-2 py-2 font-semibold"
                :class="run.status === 'failed' ? 'text-rose-700 dark:text-rose-300' : 'text-emerald-700 dark:text-emerald-300'"
              >
                {{ run.status }}
                <span
                  v-if="hasResumeMarker(run)"
                  class="ml-1 rounded-full border border-indigo-200 bg-indigo-50 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-indigo-700 dark:border-indigo-900/50 dark:bg-indigo-950/30 dark:text-indigo-200"
                >
                  resume
                </span>
              </td>
              <td class="px-2 py-2">{{ run.error_type || '-' }}</td>
              <td class="px-2 py-2" :title="run.error_message || '-'">
                <div>{{ compactMessage(run.error_message) }}</div>
                <button
                  v-if="run.error_message"
                  class="mt-1 rounded-md border border-slate-200 bg-white px-1.5 py-0.5 text-[10px] font-semibold text-slate-500 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
                  @click="copyError(run.error_message)"
                >
                  copy
                </button>
              </td>
              <td class="px-2 py-2">{{ checkpointLabel(run) }}</td>
              <td class="px-2 py-2">{{ run.duration_ms != null ? `${run.duration_ms} ms` : '-' }}</td>
              <td class="px-2 py-2" :title="formatDateTime(run.started_at) || '-'">{{ formatRelativeTime(run.started_at) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="mt-2 text-[11px] text-slate-500 dark:text-slate-400">
        Showing {{ taskRuns.length }} of {{ taskRunsCount }} run(s)
      </div>
    </section>

    <section
      class="mt-6 rounded-xl border border-amber-200 bg-amber-50/40 p-6 shadow-sm dark:border-amber-900/40 dark:bg-amber-950/20"
    >
      <div class="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h3 class="text-lg font-semibold text-slate-900 dark:text-slate-100">Delayed retries</h3>
          <p class="text-sm text-slate-500 dark:text-slate-400">
            Retry tasks waiting for backoff timeout before re-entering the queue.
          </p>
        </div>
        <div class="flex flex-wrap items-end gap-3">
          <label class="flex flex-col text-xs font-medium text-slate-600 dark:text-slate-300">
            Limit
            <input
              type="number"
              min="1"
              max="500"
              v-model.number="delayedLimit"
              class="mt-1 h-9 w-20 rounded-lg border border-slate-200 bg-white px-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            />
          </label>
          <button
            class="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 shadow-sm hover:border-slate-300 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
            :disabled="delayedLoading"
            @click="loadDelayed"
          >
            <RefreshCcw class="h-4 w-4" :class="{ 'animate-spin': delayedLoading }" />
            {{ delayedLoading ? 'Loading...' : 'Reload' }}
          </button>
        </div>
      </div>

      <div v-if="delayedItems.length === 0" class="mt-4 text-sm text-slate-500 dark:text-slate-400">
        {{ delayedLoading ? 'Loading delayed retries...' : 'No delayed retry tasks.' }}
      </div>
      <div v-else class="mt-4 overflow-x-auto">
        <table class="min-w-full text-xs">
          <thead class="text-left text-slate-500 dark:text-slate-400">
            <tr>
              <th class="px-2 py-1">Task</th>
              <th class="px-2 py-1">Due In</th>
              <th class="px-2 py-1">Due At</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(item, index) in delayedItems" :key="index" class="border-t border-slate-100 dark:border-slate-800">
              <td class="px-2 py-1.5">{{ delayedTaskLabel(item) }} (doc {{ delayedDocId(item) }})</td>
              <td class="px-2 py-1.5">{{ formatDueIn(item.due_in_seconds) }}</td>
              <td class="px-2 py-1.5">{{ item.due_at ? formatStartedAt(item.due_at) : '-' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section
      class="mt-6 rounded-xl border border-rose-200 bg-rose-50/40 p-6 shadow-sm dark:border-rose-900/40 dark:bg-rose-950/20"
    >
      <div class="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h3 class="text-lg font-semibold text-slate-900 dark:text-slate-100">Dead-letter queue</h3>
          <p class="text-sm text-slate-500 dark:text-slate-400">
            Tasks that failed after retries. Requeue manually after fixing root cause.
          </p>
        </div>
        <div class="flex flex-wrap items-end gap-3">
          <label class="flex flex-col text-xs font-medium text-slate-600 dark:text-slate-300">
            Limit
            <input
              type="number"
              min="1"
              max="500"
              v-model.number="dlqLimit"
              class="mt-1 h-9 w-20 rounded-lg border border-slate-200 bg-white px-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            />
          </label>
          <button
            class="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 shadow-sm hover:border-slate-300 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
            :disabled="dlqLoading"
            @click="loadDlq"
          >
            <RefreshCcw class="h-4 w-4" :class="{ 'animate-spin': dlqLoading }" />
            {{ dlqLoading ? 'Loading...' : 'Reload' }}
          </button>
          <button
            class="inline-flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm font-semibold text-rose-700 shadow-sm hover:border-rose-300 disabled:opacity-60 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-200"
            :disabled="dlqLoading || dlqItems.length === 0"
            @click="clearDlq"
          >
            Clear DLQ
          </button>
        </div>
      </div>

      <div v-if="dlqItems.length === 0" class="mt-4 text-sm text-slate-500 dark:text-slate-400">
        {{ dlqLoading ? 'Loading dead-letter queue...' : 'No dead-letter items.' }}
      </div>
      <div v-else class="mt-4 overflow-x-auto">
        <table class="min-w-full text-xs">
          <thead class="text-left text-slate-500 dark:text-slate-400">
            <tr>
              <th class="px-2 py-1">Task</th>
              <th class="px-2 py-1">Error Type</th>
              <th class="px-2 py-1">Attempt</th>
              <th class="px-2 py-1">Created</th>
              <th class="px-2 py-1">Action</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(item, index) in dlqItems" :key="index" class="border-t border-slate-100 dark:border-slate-800">
              <td class="px-2 py-1.5">{{ item.task?.task || 'unknown' }} (doc {{ item.task?.doc_id ?? '-' }})</td>
              <td class="px-2 py-1.5">{{ item.error_type || '-' }}</td>
              <td class="px-2 py-1.5">{{ item.attempt ?? '-' }}</td>
              <td class="px-2 py-1.5">{{ item.created_at ? formatStartedAt(item.created_at) : '-' }}</td>
              <td class="px-2 py-1.5">
                <button
                  class="rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
                  @click="requeueDlqItem(index)"
                >
                  Requeue
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAutoRefresh } from '../composables/useAutoRefresh'
import { useQueueManager } from '../composables/useQueueManager'
import type { QueueTaskRun } from '../services/queue'
import QueueOverviewSection from '../components/QueueOverviewSection.vue'
import {
  ArrowDown,
  ArrowDownToLine,
  ArrowUp,
  ArrowUpToLine,
  RefreshCcw,
  X,
} from 'lucide-vue-next'
import { formatDateTime, formatRelativeTime } from '../utils/dateTime'
import {
  formatCheckpointLabel as formatTaskCheckpointLabel,
  hasResumeMarker as taskRunHasResumeMarker,
} from '../utils/taskRunCheckpoint'
import {
  delayedDocId,
  delayedTaskLabel,
  queueCompactMessage as compactMessage,
  queueFormatDueIn as formatDueIn,
  queueFormatStartedAt as formatStartedAt,
  queueItemDescription as itemDescription,
  queueItemTitle as itemTitle,
} from '../utils/queueView'
import { useToastStore } from '../stores/toastStore'

const docIdFilter = ref('')
const router = useRouter()
const toastStore = useToastStore()
const {
  status,
  running,
  peekItems,
  taskRuns,
  taskRunsCount,
  taskRunsLoading,
  peekLimit,
  taskRunsLimit,
  taskRunsDocId,
  taskRunsTask,
  taskRunsStatus,
  taskRunsErrorType,
  taskRunsQuery,
  delayedItems,
  delayedLoading,
  delayedLimit,
  dlqItems,
  dlqLoading,
  dlqLimit,
  loading,
  peekLoading,
  busy,
  lastRefreshedAt,
  error,
  refresh,
  loadPeek,
  loadTaskRuns,
  loadDelayed,
  loadDlq,
  clearDlq: clearDlqRequest,
  requeueDlqItem: requeueDlqItemRequest,
  retryFailedRuns: retryFailedRunsRequest,
  clearQueue: clearQueueRequest,
  resetStats: resetStatsRequest,
  pauseQueue: pauseQueueRequest,
  resumeQueue: resumeQueueRequest,
  moveItem: moveItemRequest,
  moveTop: moveTopRequest,
  moveBottom: moveBottomRequest,
  removeItem: removeItemRequest,
} = useQueueManager()

const filteredItems = computed(() => {
  const needle = docIdFilter.value.trim()
  const items = peekItems.value.map((item, index) => ({ item, index }))
  if (!needle) return items
  return items.filter(({ item }) => item.doc_id != null && String(item.doc_id).includes(needle))
})

const failedTaskRuns = computed(() =>
  taskRuns.value.filter((run: QueueTaskRun) => run.status === 'failed'),
)
const recentTaskRuns = computed(() =>
  [...taskRuns.value]
    .sort((a, b) => {
      const ta = Date.parse(String(a.started_at || a.created_at || '')) || 0
      const tb = Date.parse(String(b.started_at || b.created_at || '')) || 0
      return tb - ta
    })
    .slice(0, 6),
)
const shouldAutoRefreshQueue = computed(() => {
  const inProgress = Number(status.value.in_progress || 0)
  const queued = Number(status.value.length || 0)
  return inProgress > 0 || queued > 0 || Boolean(running.value.started_at)
})

const clearQueue = async () => {
  await clearQueueRequest()
}

const resetStats = async () => {
  await resetStatsRequest()
}

const pauseQueue = async () => {
  await pauseQueueRequest()
}

const resumeQueue = async () => {
  await resumeQueueRequest()
}

const moveItem = async (fromIndex: number, toIndex: number) => {
  await moveItemRequest(fromIndex, toIndex)
}

const moveTop = async (index: number) => {
  await moveTopRequest(index)
}

const moveBottom = async (index: number) => {
  await moveBottomRequest(index)
}

const removeItem = async (index: number) => {
  await removeItemRequest(index)
}

const clearDlq = async () => {
  await clearDlqRequest()
}

const requeueDlqItem = async (index: number) => {
  await requeueDlqItemRequest(index)
}

const retryFailedTaskRuns = async () => {
  await retryFailedRunsRequest(taskRuns.value)
}

const openDocument = (docId: number) => {
  router.push(`/documents/${docId}`)
}

const copyError = async (message: string) => {
  try {
    await navigator.clipboard.writeText(message)
    toastStore.push('Error message copied.', 'success', 'Queue', 1200)
  } catch {
    toastStore.push('Failed to copy error message.', 'danger', 'Queue', 1800)
  }
}

const hasResumeMarker = (run: { checkpoint?: unknown }) => {
  const checkpoint = run.checkpoint as Record<string, unknown> | null | undefined
  return taskRunHasResumeMarker(checkpoint)
}

const checkpointLabel = (run: { checkpoint?: unknown }) => {
  const checkpoint = run.checkpoint as Record<string, unknown> | null | undefined
  return formatTaskCheckpointLabel(checkpoint, '-')
}

useAutoRefresh({
  enabled: shouldAutoRefreshQueue,
  intervalMs: 5000,
  onTick: async () => {
    await refresh()
  },
})

refresh()
</script>
