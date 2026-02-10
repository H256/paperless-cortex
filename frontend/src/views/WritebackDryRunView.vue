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
      class="flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white p-2 text-xs font-semibold text-slate-600 shadow-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
    >
      <button
        v-for="tab in tabs"
        :key="tab"
        class="rounded-lg px-3 py-1.5"
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
        <div class="flex items-center gap-2">
          <label class="inline-flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300">
            <input type="checkbox" v-model="onlyChanged" />
            Changed documents only
          </label>
          <button
            class="rounded-lg bg-slate-900 px-3 py-2 text-xs font-semibold text-white hover:bg-slate-800"
            :disabled="previewLoading"
            @click="loadPreview"
          >
            {{ previewLoading ? 'Loading...' : 'Reload preview' }}
          </button>
        </div>
        <div class="flex items-center gap-2">
          <button
            class="rounded-md border border-slate-300 px-2 py-1 hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"
            @click="selectAllChanged"
          >
            Select all changed
          </button>
          <button
            class="rounded-md border border-slate-300 px-2 py-1 hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"
            @click="clearSelection"
          >
            Clear
          </button>
          <button
            class="rounded-md bg-indigo-600 px-3 py-1 font-semibold text-white hover:bg-indigo-500 disabled:opacity-60"
            :disabled="queueLoading || selectedIds.length === 0"
            @click="enqueueSelected"
          >
            {{ queueLoading ? 'Queueing...' : `Queue selected (${selectedIds.length})` }}
          </button>
          <button
            class="rounded-md bg-emerald-600 px-3 py-1 font-semibold text-white hover:bg-emerald-500 disabled:opacity-60"
            :disabled="runLoading || selectedIds.length === 0"
            @click="runDryRunNow"
          >
            {{ runLoading ? 'Running...' : `Run dry-run now (${selectedIds.length})` }}
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
          <div class="mb-3 flex items-center justify-between gap-3">
            <label class="inline-flex items-center gap-2 text-sm font-semibold text-slate-800 dark:text-slate-100">
              <input
                type="checkbox"
                :disabled="!item.changed"
                :checked="selectedSet.has(item.doc_id)"
                @change="toggleSelect(item.doc_id)"
              />
              Document {{ item.doc_id }}
            </label>
            <span
              class="rounded-full px-2 py-1 text-[11px] font-semibold"
              :class="item.changed ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-200' : 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-200'"
            >
              {{ item.changed ? `changed: ${item.changed_fields.join(', ')}` : 'no changes' }}
            </span>
          </div>

          <div class="overflow-x-auto">
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
                  <td class="px-2 py-1 font-semibold text-slate-700 dark:text-slate-300">{{ row.field }}</td>
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
      <div class="flex items-center justify-between">
        <div class="space-y-1">
          <div class="text-sm text-slate-600 dark:text-slate-300">Pending and recent jobs</div>
          <label class="inline-flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300">
            <input type="checkbox" v-model="executeDryRunMode" />
            Execute mode: {{ executeDryRunMode ? 'Dry-run' : 'Real writeback' }}
          </label>
        </div>
        <button
          class="rounded-lg border border-slate-300 px-3 py-1 text-xs font-semibold hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"
          :disabled="jobsLoading"
          @click="loadJobs"
        >
          {{ jobsLoading ? 'Loading...' : 'Reload jobs' }}
        </button>
      </div>
      <div class="overflow-x-auto rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
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
                  :disabled="executeLoading || job.status !== 'pending'"
                  @click="runOrConfirmExecute(job.id)"
                >
                  {{ executeDryRunMode ? 'Run dry-run' : 'Run execute' }}
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
      <div class="overflow-x-auto rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
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
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import { useToastStore } from '../stores/toastStore'
import {
  createWritebackJob,
  executeWritebackJob,
  getWritebackDryRunPreview,
  listWritebackHistory,
  listWritebackJobs,
  runWritebackDryRun,
  type WritebackDryRunItem,
  type WritebackJobSummary,
} from '../services/writeback'

const toastStore = useToastStore()
const tabs = ['Preview', 'Queue', 'History'] as const
const activeTab = ref<(typeof tabs)[number]>('Preview')

const previewItems = ref<WritebackDryRunItem[]>([])
const previewLoading = ref(false)
const runLoading = ref(false)
const queueLoading = ref(false)
const onlyChanged = ref(true)
const selectedSet = ref<Set<number>>(new Set())
const errorMessage = ref('')

const jobs = ref<WritebackJobSummary[]>([])
const historyItems = ref<WritebackJobSummary[]>([])
const jobsLoading = ref(false)
const historyLoading = ref(false)
const executeLoading = ref(false)
const executeDryRunMode = ref(true)
const confirmExecuteOpen = ref(false)
const pendingExecuteJobId = ref<number | null>(null)

const selectedIds = computed(() => Array.from(selectedSet.value))

const rowsFor = (item: WritebackDryRunItem) => [
  item.title,
  item.document_date,
  item.correspondent,
  item.tags,
  item.note,
]

const noteText = (value: unknown) => {
  if (!value || typeof value !== 'object') return ''
  const text = (value as { text?: unknown }).text
  return typeof text === 'string' ? text : ''
}

const displayValue = (
  field: string,
  value: unknown,
  changed: boolean,
  side: 'original' | 'proposed',
) => {
  if (side === 'proposed' && !changed) return ''
  if (value === null || value === undefined || value === '') return '—'

  if (field === 'correspondent' && typeof value === 'object' && value !== null) {
    const v = value as { name?: unknown; id?: unknown }
    const name = typeof v.name === 'string' ? v.name : ''
    const id = typeof v.id === 'number' ? v.id : null
    if (name && id !== null) return `${name} (#${id})`
    if (name) return name
    if (id !== null) return `#${id}`
    return '—'
  }

  if (field === 'tags' && typeof value === 'object' && value !== null) {
    const v = value as { names?: unknown; ids?: unknown }
    const names = Array.isArray(v.names)
      ? v.names.map((entry) => String(entry).trim()).filter(Boolean)
      : []
    if (names.length) return names.join(', ')
    const ids = Array.isArray(v.ids) ? v.ids.map((entry) => String(entry).trim()).filter(Boolean) : []
    return ids.length ? ids.join(', ') : '—'
  }

  if (field === 'note') {
    if (typeof value === 'string') return value
    const extracted = noteText(value)
    if (extracted) return extracted
    if (typeof value === 'object' && value !== null) return '—'
  }

  if (typeof value === 'string') return value
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

const toggleSelect = (docId: number) => {
  const next = new Set(selectedSet.value)
  if (next.has(docId)) next.delete(docId)
  else next.add(docId)
  selectedSet.value = next
}

const selectAllChanged = () => {
  selectedSet.value = new Set(previewItems.value.filter((item) => item.changed).map((item) => item.doc_id))
}

const clearSelection = () => {
  selectedSet.value = new Set()
}

const loadPreview = async () => {
  previewLoading.value = true
  errorMessage.value = ''
  try {
    const data = await getWritebackDryRunPreview({
      page: 1,
      page_size: 100,
      only_changed: onlyChanged.value,
    })
    previewItems.value = data.items || []
    selectAllChanged()
  } catch (err: unknown) {
    errorMessage.value = err instanceof Error ? err.message : 'Preview could not be loaded'
  } finally {
    previewLoading.value = false
  }
}

const runDryRunNow = async () => {
  runLoading.value = true
  try {
    const result = await runWritebackDryRun(selectedIds.value)
    toastStore.push(
      `Dry-run planned ${result.calls.length} call(s) for ${result.docs_changed} changed document(s).`,
      'success',
      'Writeback',
      2400,
    )
  } catch (err: unknown) {
    toastStore.push(err instanceof Error ? err.message : 'Dry-run failed', 'danger', 'Writeback', 2800)
  } finally {
    runLoading.value = false
  }
}

const enqueueSelected = async () => {
  queueLoading.value = true
  try {
    const job = await createWritebackJob(selectedIds.value)
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
  } finally {
    queueLoading.value = false
  }
}

const loadJobs = async () => {
  jobsLoading.value = true
  try {
    jobs.value = (await listWritebackJobs(150)).items || []
    errorMessage.value = ''
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Failed to load writeback jobs'
    errorMessage.value = message
    toastStore.push(message, 'danger', 'Writeback', 3200)
  } finally {
    jobsLoading.value = false
  }
}

const executeJob = async (jobId: number, dryRun: boolean) => {
  executeLoading.value = true
  try {
    const job = await executeWritebackJob(jobId, dryRun)
    const failed = job.status === 'failed'
    toastStore.push(
      `Job #${job.id} ${job.status} (${job.calls_count} call(s)).`,
      failed ? 'danger' : 'success',
      'Writeback',
      2400,
    )
    await Promise.all([loadJobs(), loadHistory()])
  } catch (err: unknown) {
    toastStore.push(err instanceof Error ? err.message : 'Execution failed', 'danger', 'Writeback', 2800)
  } finally {
    executeLoading.value = false
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

const loadHistory = async () => {
  historyLoading.value = true
  try {
    historyItems.value = (await listWritebackHistory(150)).items || []
    errorMessage.value = ''
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Failed to load writeback history'
    errorMessage.value = message
    toastStore.push(message, 'danger', 'Writeback', 3200)
  } finally {
    historyLoading.value = false
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
</script>
