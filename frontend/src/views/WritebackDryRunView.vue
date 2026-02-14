<template>
  <section class="space-y-4">
    <div>
      <h2 class="text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">
        Writeback
      </h2>
      <p class="text-sm text-slate-500 dark:text-slate-400">
        Preview changes, queue writeback jobs, and review run history.
      </p>
    </div>

    <div
      class="overflow-x-auto rounded-xl border border-slate-200 bg-white p-2 text-xs font-semibold text-slate-600 shadow-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
    >
      <button
        v-for="tab in tabs"
        :key="tab"
        class="mr-2 inline-flex whitespace-nowrap rounded-lg px-3 py-1.5 last:mr-0"
        :class="
          activeTab === tab
            ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900'
            : 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700'
        "
        @click="activeTab = tab"
      >
        {{ tab }}
      </button>
    </div>

    <section v-if="activeTab === 'Preview'" class="space-y-4">
      <div class="flex flex-wrap items-end justify-between gap-3">
        <div class="flex w-full flex-wrap items-center gap-2 sm:w-auto">
          <label class="inline-flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300">
            <input type="checkbox" v-model="onlyChanged" />
            Changed documents only
          </label>
          <button
            class="rounded-lg bg-slate-900 px-3 py-2 text-xs font-semibold text-white hover:bg-slate-800 sm:ml-1"
            :disabled="previewLoading"
            @click="loadPreview"
          >
            {{ previewLoading ? 'Loading...' : 'Reload preview' }}
          </button>
        </div>
        <div class="flex w-full flex-wrap items-center gap-2 sm:w-auto sm:justify-end">
          <button
            class="rounded-md border border-slate-300 px-2 py-1 text-xs hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"
            @click="selectAllChanged"
          >
            Select all changed
          </button>
          <button
            class="rounded-md border border-slate-300 px-2 py-1 text-xs hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"
            @click="clearSelection"
          >
            Clear
          </button>
          <button
            class="rounded-md bg-indigo-600 px-3 py-1 text-xs font-semibold text-white hover:bg-indigo-500 disabled:opacity-60"
            :disabled="queueLoading || selectedIds.length === 0"
            @click="enqueueSelected"
          >
            {{ queueLoading ? 'Queueing...' : `Queue selected (${selectedIds.length})` }}
          </button>
        </div>
      </div>

      <div v-if="errorMessage" class="rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700 dark:border-rose-900/40 dark:bg-rose-950/30 dark:text-rose-200">
        {{ errorMessage }}
      </div>

      <div class="space-y-3" :class="previewLoading ? 'opacity-60' : ''">
        <article
          v-for="item in previewItems"
          :key="item.doc_id"
          class="rounded-xl border bg-white p-4 shadow-sm dark:bg-slate-900"
          :class="item.changed ? 'border-amber-300 dark:border-amber-700/50' : 'border-slate-200 dark:border-slate-800'"
        >
          <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
            <label class="inline-flex items-center gap-2 text-sm font-semibold text-slate-800 dark:text-slate-100">
              <input
                type="checkbox"
                :disabled="!item.changed"
                :checked="selectedSet.has(item.doc_id)"
                @change="toggleSelect(item.doc_id)"
              />
              Document {{ item.doc_id }}
            </label>
            <div class="flex w-full flex-wrap items-center gap-2 sm:w-auto sm:justify-end">
              <a
                :href="documentLink(item.doc_id)"
                target="_blank"
                rel="noopener noreferrer"
                class="inline-flex items-center gap-1 rounded-md border border-slate-300 px-2 py-1 text-[11px] font-semibold text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
              >
                Open
                <ExternalLink class="h-3.5 w-3.5" />
              </a>
              <span
                class="rounded-full px-2 py-1 text-[11px] font-semibold"
                :class="item.changed ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-200' : 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-200'"
              >
                {{ item.changed ? `changed: ${(item.changed_fields || []).map(fieldLabel).join(', ')}` : 'no changes' }}
              </span>
            </div>
          </div>

          <div class="space-y-2 md:hidden">
            <div
              v-for="row in rowsFor(item)"
              :key="`mobile-${item.doc_id}-${row.field}`"
              class="rounded-lg border p-2 text-xs dark:border-slate-700"
              :class="row.changed ? 'border-amber-200 bg-amber-50/60 dark:border-amber-800/40 dark:bg-amber-900/10' : 'border-slate-200 bg-slate-50/50 dark:border-slate-800 dark:bg-slate-800/40'"
            >
              <div class="font-semibold text-slate-700 dark:text-slate-200">{{ fieldLabel(row.field) }}</div>
              <div class="mt-1 text-[11px] text-slate-500 dark:text-slate-400">Original</div>
              <div class="whitespace-pre-wrap text-slate-700 dark:text-slate-200">
                {{ displayValue(row.field, row.original, row.changed, 'original') }}
              </div>
              <div class="mt-2 text-[11px] text-slate-500 dark:text-slate-400">New</div>
              <div
                class="whitespace-pre-wrap"
                :class="row.changed ? 'font-semibold text-amber-800 dark:text-amber-200' : 'text-slate-400 dark:text-slate-500'"
              >
                {{ displayValue(row.field, row.proposed, row.changed, 'proposed') }}
              </div>
            </div>
          </div>

          <div class="hidden overflow-x-auto md:block">
            <table class="min-w-full table-fixed text-xs">
              <colgroup>
                <col class="w-32" />
                <col class="w-1/2" />
                <col class="w-1/2" />
              </colgroup>
              <thead>
                <tr class="text-left text-slate-500 dark:text-slate-400">
                  <th class="px-2 py-1">Field</th>
                  <th class="px-2 py-1">Original</th>
                  <th class="px-2 py-1">New</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in rowsFor(item)" :key="row.field" :class="row.changed ? 'bg-amber-50/70 dark:bg-amber-900/10' : ''">
                  <td class="px-2 py-1 font-semibold text-slate-700 dark:text-slate-300">{{ fieldLabel(row.field) }}</td>
                  <td class="px-2 py-1 text-slate-700 dark:text-slate-200 whitespace-pre-wrap">{{ displayValue(row.field, row.original, row.changed, 'original') }}</td>
                  <td class="px-2 py-1 whitespace-pre-wrap" :class="row.changed ? 'font-semibold text-amber-800 dark:text-amber-200' : 'text-slate-400 dark:text-slate-500'">
                    {{ displayValue(row.field, row.proposed, row.changed, 'proposed') }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </article>
      </div>
    </section>

    <section v-if="activeTab === 'Queue'" class="space-y-4">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div class="space-y-1">
          <div class="text-sm text-slate-600 dark:text-slate-300">Pending and recent jobs</div>
          <label class="inline-flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300">
            <input type="checkbox" v-model="executeDryRunMode" />
            Execute mode: {{ executeDryRunMode ? 'Dry-run' : 'Real writeback' }}
          </label>
        </div>
        <div class="flex w-full flex-wrap items-center gap-2 sm:w-auto sm:justify-end">
          <button
            class="rounded-lg px-3 py-1 text-xs font-semibold text-white disabled:opacity-60"
            :class="executeDryRunMode ? 'bg-emerald-600 hover:bg-emerald-500' : 'bg-amber-600 hover:bg-amber-500'"
            :disabled="executeAllLoading || pendingCount === 0"
            @click="runOrConfirmExecuteAll"
          >
            {{ executeAllLoading ? 'Running...' : executeDryRunMode ? 'Run all pending (dry-run)' : 'Run all pending (execute)' }}
          </button>
          <button
            class="rounded-lg border border-slate-300 px-3 py-1 text-xs font-semibold hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"
            :disabled="jobsLoading"
            @click="loadJobs"
          >
            {{ jobsLoading ? 'Loading...' : 'Reload jobs' }}
          </button>
        </div>
      </div>
      <div
        v-if="lastExecuteAllResults.length > 0"
        class="rounded-xl border border-slate-200 bg-white p-3 text-xs shadow-sm dark:border-slate-800 dark:bg-slate-900"
      >
        <div class="mb-2 flex items-center justify-between gap-2">
          <div class="font-semibold text-slate-700 dark:text-slate-200">Last bulk run details</div>
          <button
            class="rounded-md border border-slate-300 px-2 py-1 text-[11px] font-semibold hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"
            @click="lastExecuteAllResults = []"
          >
            Clear
          </button>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-xs">
            <thead class="bg-slate-50 text-left text-slate-500 dark:bg-slate-800 dark:text-slate-400">
              <tr>
                <th class="px-3 py-2">Job</th>
                <th class="px-3 py-2">Status</th>
                <th class="px-3 py-2">Mode</th>
                <th class="px-3 py-2">Docs</th>
                <th class="px-3 py-2">Calls</th>
                <th class="px-3 py-2">Error</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="result in lastExecuteAllResults"
                :key="result.job_id"
                class="border-t border-slate-100 dark:border-slate-800"
              >
                <td class="px-3 py-2 font-semibold">#{{ result.job_id }}</td>
                <td
                  class="px-3 py-2 font-semibold"
                  :class="result.status === 'completed' ? 'text-emerald-700 dark:text-emerald-300' : 'text-rose-700 dark:text-rose-300'"
                >
                  {{ result.status }}
                </td>
                <td class="px-3 py-2">{{ result.dry_run ? 'Dry-run' : 'Execute' }}</td>
                <td class="px-3 py-2">{{ result.docs_changed }}/{{ result.docs_selected }}</td>
                <td class="px-3 py-2">{{ result.calls_count }}</td>
                <td class="px-3 py-2 text-rose-700 dark:text-rose-300">{{ result.error || '-' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <div class="space-y-2 md:hidden">
        <article
          v-for="job in jobs"
          :key="`job-mobile-${job.id}`"
          class="rounded-xl border border-slate-200 bg-white p-3 text-xs dark:border-slate-800 dark:bg-slate-900"
        >
          <div class="flex items-center justify-between gap-2">
            <div class="font-semibold">#{{ job.id }}</div>
            <div>{{ job.status }}</div>
          </div>
          <div class="mt-1 text-slate-600 dark:text-slate-300">{{ job.dry_run ? 'Dry-run' : 'Execute' }}</div>
          <div class="mt-1 text-slate-600 dark:text-slate-300">Docs: {{ job.docs_changed }}/{{ job.docs_selected }}</div>
          <div class="mt-1 text-slate-600 dark:text-slate-300">Calls: {{ job.calls_count }}</div>
          <div class="mt-1 text-slate-500 dark:text-slate-400">{{ formatDateTime(job.created_at) }}</div>
          <div class="mt-2 flex flex-wrap gap-2">
            <button
              class="rounded-md px-2 py-1 font-semibold text-white disabled:opacity-60"
              :class="executeDryRunMode ? 'bg-emerald-600 hover:bg-emerald-500' : 'bg-amber-600 hover:bg-amber-500'"
              :disabled="executeLoading || deleteLoading || job.status !== 'pending'"
              @click="runOrConfirmExecute(job.id)"
            >
              {{ executeDryRunMode ? 'Run dry-run' : 'Run execute' }}
            </button>
            <button
              class="rounded-md border border-rose-300 px-2 py-1 font-semibold text-rose-700 hover:bg-rose-50 disabled:opacity-60 dark:border-rose-900/60 dark:text-rose-300 dark:hover:bg-rose-950/30"
              :disabled="deleteLoading || job.status !== 'pending'"
              @click="removeQueuedJob(job.id)"
            >
              Remove
            </button>
          </div>
        </article>
      </div>
      <div class="hidden overflow-x-auto rounded-xl border border-slate-200 bg-white md:block dark:border-slate-800 dark:bg-slate-900">
        <table class="w-full text-xs">
          <thead class="bg-slate-50 text-left text-slate-500 dark:bg-slate-800 dark:text-slate-400">
            <tr>
              <th class="px-3 py-2">Job</th>
              <th class="px-3 py-2">Status</th>
              <th class="px-3 py-2">Mode</th>
              <th class="px-3 py-2">Docs</th>
              <th class="px-3 py-2">Calls</th>
              <th class="px-3 py-2">Created</th>
              <th class="px-3 py-2">Action</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="job in jobs" :key="job.id" class="border-t border-slate-100 dark:border-slate-800">
              <td class="px-3 py-2 font-semibold">#{{ job.id }}</td>
              <td class="px-3 py-2">{{ job.status }}</td>
              <td class="px-3 py-2">{{ job.dry_run ? 'Dry-run' : 'Execute' }}</td>
              <td class="px-3 py-2">{{ job.docs_changed }}/{{ job.docs_selected }}</td>
              <td class="px-3 py-2">{{ job.calls_count }}</td>
              <td class="px-3 py-2">{{ formatDateTime(job.created_at) }}</td>
              <td class="px-3 py-2">
                <button
                  class="rounded-md px-2 py-1 font-semibold text-white disabled:opacity-60"
                  :class="executeDryRunMode ? 'bg-emerald-600 hover:bg-emerald-500' : 'bg-amber-600 hover:bg-amber-500'"
                  :disabled="executeLoading || deleteLoading || job.status !== 'pending'"
                  @click="runOrConfirmExecute(job.id)"
                >
                  {{ executeDryRunMode ? 'Run dry-run' : 'Run execute' }}
                </button>
                <button
                  class="ml-2 rounded-md border border-rose-300 px-2 py-1 font-semibold text-rose-700 hover:bg-rose-50 disabled:opacity-60 dark:border-rose-900/60 dark:text-rose-300 dark:hover:bg-rose-950/30"
                  :disabled="deleteLoading || job.status !== 'pending'"
                  @click="removeQueuedJob(job.id)"
                >
                  Remove
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section v-if="activeTab === 'History'" class="space-y-4">
      <div class="flex items-center justify-between">
        <div class="text-sm text-slate-600 dark:text-slate-300">Completed runs</div>
        <button
          class="rounded-lg border border-slate-300 px-3 py-1 text-xs font-semibold hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"
          :disabled="historyLoading"
          @click="loadHistory"
        >
          {{ historyLoading ? 'Loading...' : 'Reload history' }}
        </button>
      </div>
      <div class="space-y-2 md:hidden">
        <article
          v-for="job in historyItems"
          :key="`history-mobile-${job.id}`"
          class="rounded-xl border border-slate-200 bg-white p-3 text-xs dark:border-slate-800 dark:bg-slate-900"
        >
          <div class="flex items-center justify-between gap-2">
            <div class="font-semibold">#{{ job.id }}</div>
            <div>{{ job.status }}</div>
          </div>
          <div class="mt-1 text-slate-600 dark:text-slate-300">{{ job.dry_run ? 'Dry-run' : 'Execute' }}</div>
          <div class="mt-1 text-slate-600 dark:text-slate-300">Docs: {{ job.docs_changed }}/{{ job.docs_selected }}</div>
          <div class="mt-1 text-slate-600 dark:text-slate-300">Calls: {{ job.calls_count }}</div>
          <div class="mt-1 text-slate-500 dark:text-slate-400">{{ formatDateTime(job.finished_at || job.created_at) }}</div>
        </article>
      </div>
      <div class="hidden overflow-x-auto rounded-xl border border-slate-200 bg-white md:block dark:border-slate-800 dark:bg-slate-900">
        <table class="w-full text-xs">
          <thead class="bg-slate-50 text-left text-slate-500 dark:bg-slate-800 dark:text-slate-400">
            <tr>
              <th class="px-3 py-2">Job</th>
              <th class="px-3 py-2">Status</th>
              <th class="px-3 py-2">Mode</th>
              <th class="px-3 py-2">Docs</th>
              <th class="px-3 py-2">Calls</th>
              <th class="px-3 py-2">Finished</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="job in historyItems" :key="job.id" class="border-t border-slate-100 dark:border-slate-800">
              <td class="px-3 py-2 font-semibold">#{{ job.id }}</td>
              <td class="px-3 py-2">{{ job.status }}</td>
              <td class="px-3 py-2">{{ job.dry_run ? 'Dry-run' : 'Execute' }}</td>
              <td class="px-3 py-2">{{ job.docs_changed }}/{{ job.docs_selected }}</td>
              <td class="px-3 py-2">{{ job.calls_count }}</td>
              <td class="px-3 py-2">{{ formatDateTime(job.finished_at || job.created_at) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <ConfirmDialog
      :open="confirmExecuteOpen"
      title="Run real writeback?"
      message="This will call Paperless write endpoints for this job. Dry-run stays available if you cancel."
      confirm-label="Run execute"
      cancel-label="Cancel"
      @confirm="confirmExecute"
      @cancel="cancelExecute"
    />
    <ConfirmDialog
      :open="confirmExecuteAllOpen"
      title="Run all pending with real writeback?"
      message="This executes all pending jobs against Paperless write endpoints."
      confirm-label="Run all execute"
      cancel-label="Cancel"
      @confirm="confirmExecuteAll"
      @cancel="cancelExecuteAll"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ExternalLink } from 'lucide-vue-next'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import { useToastStore } from '../stores/toastStore'
import { useWritebackManager } from '../composables/useWritebackManager'
import {
  rowsForWritebackItem,
  writebackDisplayValue,
  writebackFieldLabel,
} from '../utils/writebackPreview'

const toastStore = useToastStore()
const tabs = ['Preview', 'Queue', 'History'] as const
const activeTab = ref<(typeof tabs)[number]>('Preview')
const errorMessage = ref('')
const executeDryRunMode = ref(true)
const confirmExecuteOpen = ref(false)
const pendingExecuteJobId = ref<number | null>(null)
const confirmExecuteAllOpen = ref(false)

const writeback = useWritebackManager()
const onlyChanged = writeback.onlyChanged
const selectedSet = writeback.selectedSet
const selectedIds = writeback.selectedIds
const previewItems = writeback.previewItems
const jobs = writeback.jobs
const historyItems = writeback.historyItems
const pendingCount = writeback.pendingCount
const lastExecuteAllResults = writeback.lastExecuteAllResults

const previewLoading = computed(() => writeback.previewQuery.isFetching.value)
const jobsLoading = computed(() => writeback.jobsQuery.isFetching.value)
const historyLoading = computed(() => writeback.historyQuery.isFetching.value)
const queueLoading = computed(() => writeback.enqueueMutation.isPending.value)
const executeLoading = computed(() => writeback.executeJobMutation.isPending.value)
const executeAllLoading = computed(() => writeback.executeAllMutation.isPending.value)
const deleteLoading = computed(() => writeback.deleteJobMutation.isPending.value)

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || '/api'
const baseOrigin = window.location.origin
const paperlessBase = import.meta.env.VITE_PAPERLESS_BASE_URL || ''

const rowsFor = rowsForWritebackItem
const fieldLabel = writebackFieldLabel
const displayValue = writebackDisplayValue

const toggleSelect = writeback.toggleSelect
const selectAllChanged = writeback.selectAllChanged
const clearSelection = writeback.clearSelection

const removeDocsFromPreview = (docIds: number[]) => {
  if (!docIds.length) return
  const idSet = new Set(docIds.map((v) => Number(v)))
  selectedSet.value = new Set(
    Array.from(selectedSet.value).filter((docId) => !idSet.has(Number(docId))),
  )
}

const documentLink = (docId: number) => {
  if (paperlessBase) {
    return `${String(paperlessBase).replace(/\/$/, '')}/documents/${docId}`
  }
  const api = apiBaseUrl.startsWith('http')
    ? apiBaseUrl
    : `${baseOrigin}${apiBaseUrl.startsWith('/') ? apiBaseUrl : `/${apiBaseUrl}`}`
  return `${api.replace(/\/api\/?$/, '')}/documents/${docId}`
}

const loadPreview = async () => {
  errorMessage.value = ''
  try {
    await writeback.reloadPreview()
  } catch (err: unknown) {
    errorMessage.value = err instanceof Error ? err.message : 'Preview could not be loaded'
  }
}

const enqueueSelected = async () => {
  try {
    const job = await writeback.enqueueMutation.mutateAsync(selectedIds.value)
    toastStore.push(
      `Queued job #${job.id} (${job.calls_count} planned call(s)).`,
      'success',
      'Writeback',
      2400,
    )
    await loadJobs()
    activeTab.value = 'Queue'
  } catch (err: unknown) {
    toastStore.push(err instanceof Error ? err.message : 'Queueing failed', 'danger', 'Writeback', 2800)
  }
}

const loadJobs = async () => {
  try {
    await writeback.reloadJobs()
    errorMessage.value = ''
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Failed to load writeback jobs'
    errorMessage.value = message
    toastStore.push(message, 'danger', 'Writeback', 3200)
  }
}

const removeQueuedJob = async (jobId: number) => {
  try {
    const result = await writeback.deleteJobMutation.mutateAsync(jobId)
    if (result.removed) {
      toastStore.push(`Removed job #${jobId} from queue.`, 'success', 'Writeback', 2200)
    } else {
      toastStore.push(`Job #${jobId} not found.`, 'warning', 'Writeback', 2200)
    }
    await loadJobs()
  } catch (err: unknown) {
    toastStore.push(
      err instanceof Error ? err.message : 'Failed to remove writeback job',
      'danger',
      'Writeback',
      2800,
    )
  }
}

const executeJob = async (jobId: number, dryRun: boolean) => {
  try {
    const job = await writeback.executeJobMutation.mutateAsync({ jobId, dryRun })
    const failed = job.status === 'failed'
    toastStore.push(
      `Job #${job.id} ${job.status} (${job.calls_count} call(s)).`,
      failed ? 'danger' : 'success',
      'Writeback',
      2400,
    )
    if (!dryRun && job.status === 'completed') removeDocsFromPreview(job.doc_ids || [])
    await Promise.all([loadJobs(), loadHistory()])
  } catch (err: unknown) {
    toastStore.push(err instanceof Error ? err.message : 'Execution failed', 'danger', 'Writeback', 2800)
  }
}

const runOrConfirmExecute = (jobId: number) => {
  if (executeDryRunMode.value) {
    executeJob(jobId, true)
    return
  }
  pendingExecuteJobId.value = jobId
  confirmExecuteOpen.value = true
}

const confirmExecute = async () => {
  const jobId = pendingExecuteJobId.value
  confirmExecuteOpen.value = false
  pendingExecuteJobId.value = null
  if (!jobId) return
  await executeJob(jobId, false)
}

const cancelExecute = () => {
  confirmExecuteOpen.value = false
  pendingExecuteJobId.value = null
}

const executeAllPending = async (dryRun: boolean) => {
  try {
    const result = await writeback.executeAllMutation.mutateAsync({ dryRun, limit: 0 })
    const tone = result.failed > 0 ? 'warning' : 'success'
    toastStore.push(
      `Processed ${result.processed} pending job(s): ${result.completed} completed, ${result.failed} failed.`,
      tone,
      'Writeback',
      3000,
    )
    if (!dryRun && result.completed > 0) {
      removeDocsFromPreview(result.doc_ids || [])
    }
    await Promise.all([loadJobs(), loadHistory()])
  } catch (err: unknown) {
    lastExecuteAllResults.value = []
    toastStore.push(err instanceof Error ? err.message : 'Run all pending failed', 'danger', 'Writeback', 3200)
  }
}

const runOrConfirmExecuteAll = () => {
  if (executeDryRunMode.value) {
    executeAllPending(true)
    return
  }
  confirmExecuteAllOpen.value = true
}

const confirmExecuteAll = async () => {
  confirmExecuteAllOpen.value = false
  await executeAllPending(false)
}

const cancelExecuteAll = () => {
  confirmExecuteAllOpen.value = false
}

const loadHistory = async () => {
  try {
    await writeback.reloadHistory()
    errorMessage.value = ''
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Failed to load writeback history'
    errorMessage.value = message
    toastStore.push(message, 'danger', 'Writeback', 3200)
  }
}

const formatDateTime = (value?: string | null) => {
  if (!value) return '-'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return new Intl.DateTimeFormat(navigator.language, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(parsed)
}

onMounted(async () => {
  await Promise.allSettled([loadPreview(), loadJobs(), loadHistory()])
})

watch(onlyChanged, () => {
  void loadPreview()
})
</script>
