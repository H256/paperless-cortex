<template>
  <div
    v-if="open"
    class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4"
  >
    <div
      class="w-full max-w-xl rounded-2xl border border-slate-200 bg-white p-6 shadow-xl dark:border-slate-800 dark:bg-slate-900"
    >
      <div class="flex items-center justify-between">
        <div>
          <h3 class="text-lg font-semibold text-slate-900 dark:text-slate-100">Ready to process</h3>
          <p class="text-xs text-slate-500 dark:text-slate-400">
            Summary of missing intelligence tasks
          </p>
        </div>
      </div>

      <div
        v-if="syncStatus.status === 'running'"
        class="mt-4 rounded-lg border border-indigo-200 bg-indigo-50 p-3 text-xs text-indigo-700 dark:border-indigo-900/50 dark:bg-indigo-950/40 dark:text-indigo-200"
      >
        <div class="flex items-center gap-2">
          <Loader2 class="h-4 w-4 animate-spin" />
          Sync {{ syncStatus.processed }} / {{ syncStatus.total }} ({{ progressPercent }}%) - ETA
          {{ etaText }}
        </div>
        <div class="mt-1 text-[11px] text-indigo-600/80 dark:text-indigo-200/70">
          Sync is running. Start is available as soon as sync is complete.
        </div>
      </div>
      <div
        v-if="processPreviewLoading"
        class="mt-4 text-sm text-slate-500 dark:text-slate-400"
      >
        Calculating...
      </div>
      <div v-else class="mt-4 grid gap-3 sm:grid-cols-2">
        <div
          class="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-800 dark:text-slate-200"
        >
          <div class="text-xs uppercase text-slate-400">Documents</div>
          <div class="mt-1 text-lg font-semibold text-slate-900 dark:text-slate-100">
            {{ processPreview?.docs ?? 0 }}
          </div>
          <div class="mt-1 text-xs text-slate-500">Total checked</div>
        </div>
        <div
          class="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-800 dark:text-slate-200"
        >
          <div class="text-xs uppercase text-slate-400">Needs work</div>
          <div class="mt-1 text-lg font-semibold text-slate-900 dark:text-slate-100">
            {{ processPreview?.missing_docs ?? 0 }}
          </div>
          <div class="mt-1 text-xs text-slate-500">Documents to process</div>
        </div>
      </div>

      <div
        v-if="!processPreviewLoading && processPreview"
        class="mt-4 rounded-lg border border-slate-200 bg-white p-4 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
      >
        <div class="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          Pipeline coverage
        </div>
        <div class="mt-2 grid gap-2 sm:grid-cols-2">
          <div
            v-for="item in coverageItems"
            :key="item.key"
            class="flex items-center justify-between rounded-md border border-slate-200 bg-slate-50 px-2 py-1.5 dark:border-slate-700 dark:bg-slate-800"
          >
            <span>{{ item.label }}</span>
            <span
              class="font-semibold"
              :class="item.missing > 0 ? 'text-amber-600 dark:text-amber-300' : 'text-emerald-600 dark:text-emerald-300'"
            >
              {{ item.missing > 0 ? `${item.missing} missing` : 'covered' }}
            </span>
          </div>
        </div>
      </div>

      <div
        v-if="!processPreviewLoading && processPreview"
        class="mt-4 rounded-lg border border-slate-200 bg-white p-4 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
      >
        <div class="flex items-center justify-between gap-2">
          <div class="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Detailed Missing Counters
          </div>
          <button
            class="rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
            @click="toggleDetailedCounters"
          >
            {{ showDetailedCounters ? 'Hide details' : 'Show details' }}
          </button>
        </div>
        <label
          v-if="showDetailedCounters"
          class="mt-2 inline-flex items-center gap-1.5 text-[11px] text-slate-500 dark:text-slate-400"
        >
          <input v-model="showOnlyNonZeroCounters" type="checkbox" class="h-3.5 w-3.5" />
          Show only non-zero
        </label>
        <div v-if="showDetailedCounters" class="mt-2 grid gap-2 sm:grid-cols-2">
          <div
            v-for="item in visibleDetailedCounters"
            :key="item.key"
            class="rounded-md border border-slate-200 bg-slate-50 px-2 py-1.5 dark:border-slate-700 dark:bg-slate-800"
          >
            {{ item.label }}:
            <strong class="text-slate-900 dark:text-slate-100">{{ item.value }}</strong>
          </div>
        </div>
      </div>

      <div
        v-if="!processPreviewLoading && previewDocs.length"
        class="mt-4 rounded-lg border border-slate-200 bg-white p-4 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
      >
        <div class="flex items-center justify-between gap-2">
          <div class="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Sample Documents With Gaps
          </div>
          <div
            v-if="highPriorityPreviewCount > 0"
            class="rounded-md border border-amber-300 bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-700 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-300"
          >
            {{ highPriorityPreviewCount }} high-priority
          </div>
        </div>
        <div class="mt-2 max-h-40 space-y-1 overflow-auto pr-1">
          <div
            v-for="item in prioritizedPreviewDocs"
            :key="item.doc_id"
            class="flex items-start justify-between gap-2 rounded-md border px-2 py-1.5"
            :class="isHighPriorityPreviewDoc(item)
              ? 'border-amber-300 bg-amber-50/70 dark:border-amber-900/50 dark:bg-amber-950/20'
              : 'border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-800'"
          >
            <div class="min-w-0">
              <div class="flex items-center gap-2">
                <button
                  class="truncate text-left font-semibold text-slate-800 underline-offset-2 hover:underline dark:text-slate-100"
                  :title="`Open document ${item.doc_id}`"
                  @click="$emit('open-doc', item.doc_id)"
                >
                  #{{ item.doc_id }} {{ item.title || 'Untitled' }}
                </button>
                <span
                  v-if="isHighPriorityPreviewDoc(item)"
                  class="shrink-0 rounded border border-amber-300 bg-amber-50 px-1.5 py-0.5 text-[10px] font-semibold text-amber-700 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-300"
                >
                  priority
                </span>
              </div>
              <div class="truncate text-[11px] text-slate-500 dark:text-slate-400">
                {{ (item.missing_tasks || []).join(', ') || '-' }}
              </div>
            </div>
            <div class="shrink-0 text-right">
              <div
                v-if="isHighPriorityPreviewDoc(item)"
                class="text-[11px] font-semibold text-amber-700 dark:text-amber-300"
              >
                High priority
              </div>
              <div class="text-[11px] font-semibold text-amber-600 dark:text-amber-300">
                {{ formatMissingSteps(item.missing_steps) }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div
        v-if="!processPreviewLoading && processPreview"
        class="mt-4 rounded-lg border border-slate-200 bg-white p-3 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
      >
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div>
            Expected enqueue:
            <strong class="text-slate-900 dark:text-slate-100">up to {{ expectedEnqueueDocs }} docs</strong>
            <span class="text-slate-500 dark:text-slate-400"> ({{ expectedEnqueueTasksLabel }})</span>
          </div>
          <div
            class="rounded-md border px-2 py-0.5 text-[11px] font-semibold"
            :class="canStartProcessing
              ? 'border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-900/50 dark:bg-emerald-950/30 dark:text-emerald-300'
              : 'border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-300'"
          >
            {{ canStartProcessing ? 'Ready to enqueue' : startDisabledReason }}
          </div>
        </div>
      </div>

      <div
        class="mt-6 rounded-lg border border-slate-200 bg-slate-50 p-4 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
      >
        <div
          class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500"
        >
          Processing options
        </div>
        <div class="mt-3 grid gap-3 sm:grid-cols-2">
          <div
            class="flex flex-col gap-2 text-xs font-medium text-slate-700 dark:text-slate-200 sm:col-span-2"
          >
            <label for="batch-index" class="text-xs font-medium text-slate-700 dark:text-slate-200">
              Max documents to process
            </label>
            <div class="flex items-center gap-3">
              <input
                id="batch-index"
                v-model.number="batchIndexModel"
                type="range"
                :min="0"
                :max="batchOptions.length - 1"
                step="1"
                class="h-2 w-full cursor-pointer accent-indigo-600"
              />
              <span
                class="min-w-[3.5rem] text-right text-sm font-semibold text-slate-900 dark:text-slate-100"
              >
                {{ batchLabel }}
              </span>
            </div>
            <span class="text-[11px] text-slate-400 dark:text-slate-500">
              Use a smaller batch if your LLM server is not always online.
            </span>
          </div>
          <label
            class="flex items-center gap-2 text-xs font-medium text-slate-700 dark:text-slate-200 sm:col-span-2"
          >
            <input
              type="checkbox"
              v-model="processOptions.includeSync"
              class="h-4 w-4 rounded border-slate-300 text-indigo-600"
            />
            Sync from Paperless first (insert missing docs + mark deleted)
          </label>
          <label class="flex flex-col gap-1 text-xs font-medium text-slate-700 dark:text-slate-200 sm:col-span-2">
            Processing strategy
            <select
              v-model="processOptions.strategy"
              class="rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            >
              <option value="balanced">Balanced (Recommended)</option>
              <option value="vision_first">Vision first</option>
              <option value="paperless_only">Paperless only</option>
              <option value="max_coverage">Max coverage (both sources)</option>
            </select>
          </label>
          <div
            v-if="recommendedStrategyInfo"
            class="flex items-center justify-between gap-2 rounded-md border border-indigo-200 bg-indigo-50 px-2 py-1.5 text-[11px] text-indigo-700 dark:border-indigo-900/50 dark:bg-indigo-950/30 dark:text-indigo-300 sm:col-span-2"
          >
            <div>
              Recommended now:
              <strong>{{ strategyLabel(recommendedStrategyInfo.strategy) }}</strong>
              <span v-if="recommendedStrategyInfo.reason"> ({{ recommendedStrategyInfo.reason }})</span>
            </div>
            <button
              v-if="processOptions.strategy !== recommendedStrategyInfo.strategy"
              class="rounded-md border border-indigo-300 bg-white px-2 py-0.5 text-[11px] font-semibold text-indigo-700 hover:border-indigo-400 dark:border-indigo-700 dark:bg-slate-900 dark:text-indigo-300"
              @click="applyRecommendedStrategy"
            >
              Use recommended
            </button>
          </div>
          <div class="rounded-md border border-slate-200 bg-white p-2 text-[11px] text-slate-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 sm:col-span-2">
            {{ strategyHint }}
          </div>
          <div
            v-if="strategyWarnings.length"
            class="rounded-md border border-amber-300 bg-amber-50 p-2 text-[11px] text-amber-700 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-300 sm:col-span-2"
          >
            <div v-for="warning in strategyWarnings" :key="warning">
              {{ warning }}
            </div>
          </div>
        </div>
      </div>

      <div
        class="mt-4 rounded-lg border border-slate-200 bg-white p-4 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
      >
        <div class="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          What Happens Next
        </div>
        <ol class="mt-2 space-y-1.5 list-decimal pl-4">
          <li v-for="step in executionPlanSteps" :key="step">
            {{ step }}
          </li>
        </ol>
      </div>

      <div
        class="mt-4 rounded-lg border border-slate-200 bg-white p-4 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
      >
        <div class="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          Runtime state
        </div>
        <div class="mt-2 grid gap-2 sm:grid-cols-3">
          <div class="rounded-md border border-slate-200 bg-slate-50 px-2 py-1.5 dark:border-slate-700 dark:bg-slate-800">
            Queue: <strong>{{ queueEnabled ? 'enabled' : 'disabled' }}</strong>
          </div>
          <div class="rounded-md border border-slate-200 bg-slate-50 px-2 py-1.5 dark:border-slate-700 dark:bg-slate-800">
            Queued items: <strong>{{ queueLengthLabel }}</strong>
          </div>
          <div class="rounded-md border border-slate-200 bg-slate-50 px-2 py-1.5 dark:border-slate-700 dark:bg-slate-800">
            Worker activity: <strong>{{ processingActive ? 'active' : 'idle' }}</strong>
          </div>
        </div>
        <div
          v-if="!queueEnabled"
          class="mt-2 rounded-md border border-rose-200 bg-rose-50 px-2 py-1.5 text-rose-700 dark:border-rose-900/40 dark:bg-rose-950/30 dark:text-rose-300"
        >
          Queue is disabled. Starting processing will not enqueue work.
        </div>
      </div>

      <div
        v-if="processStartResult"
        class="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-xs text-emerald-700 dark:border-emerald-900/40 dark:bg-emerald-950/30 dark:text-emerald-300"
      >
        Enqueued {{ processStartResult.enqueued ?? 0 }} documents and
        {{ processStartResult.tasks ?? 0 }} tasks. Use Queue/Document timeline to monitor progress.
      </div>

      <div class="mt-6 flex flex-wrap items-center justify-end gap-3">
        <button
          v-if="processStartResult"
          class="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
          @click="$emit('close')"
        >
          Close and monitor
        </button>
        <template v-else>
          <button
            class="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
            @click="$emit('close')"
            :disabled="processStartLoading"
          >
            Cancel
          </button>
          <button
            class="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500"
            :class="{
              'cursor-not-allowed opacity-60':
                processPreviewLoading ||
                processStartLoading ||
                syncing ||
                isSyncingNow ||
                !queueEnabled ||
                !canStartProcessing,
            }"
            :disabled="
              processPreviewLoading ||
              processStartLoading ||
              syncing ||
              isSyncingNow ||
              !queueEnabled ||
              !canStartProcessing
            "
            @click="$emit('start')"
          >
            <span v-if="processStartLoading" class="inline-flex items-center gap-2">
              <Loader2 class="h-4 w-4 animate-spin" />
              Enqueuing...
            </span>
            <span v-else-if="isSyncingNow">Syncing...</span>
            <span v-else>Start processing (enqueue)</span>
          </button>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Loader2 } from 'lucide-vue-next'
import type { ProcessMissingResponse, SyncStatusResponse } from '@/api/generated/model'

type ProcessOptions = {
  includeSync: boolean
  strategy: 'balanced' | 'paperless_only' | 'vision_first' | 'max_coverage'
}

type PreviewDocItem = {
  doc_id: number
  title: string
  missing_steps: string[]
  missing_tasks: string[]
}

const props = defineProps<{
  open: boolean
  syncStatus: SyncStatusResponse
  progressPercent: number
  etaText: string
  processPreviewLoading: boolean
  processPreview: ProcessMissingResponse | null
  processOptions: ProcessOptions
  batchIndex: number
  batchOptions: readonly (number | 'All')[]
  batchLabel: string
  processStartResult: { enqueued?: number; tasks?: number } | null
  processStartLoading: boolean
  syncing: boolean
  isSyncingNow: boolean
  queueEnabled: boolean
  queueLength: number | null
  processingActive: boolean
}>()

const emit = defineEmits<{
  close: []
  start: []
  'open-doc': [docId: number]
  'update:batchIndex': [value: number]
}>()

const batchIndexModel = computed({
  get: () => props.batchIndex,
  set: (value: number) => emit('update:batchIndex', value),
})

const coverageItems = computed(() => {
  const preview = props.processPreview
  if (!preview) return []
  const stepCounts = (preview.missing_by_step || {}) as Record<string, number>
  return [
    {
      key: 'paperless',
      label: 'Paperless baseline',
      missing: Number(stepCounts.paperless ?? 0),
    },
    {
      key: 'vision',
      label: 'Vision pipeline',
      missing: Number(stepCounts.vision ?? 0),
    },
    {
      key: 'large',
      label: 'Large-document extras',
      missing: Number(stepCounts.large ?? 0),
    },
    {
      key: 'overall',
      label: 'Overall docs with gaps',
      missing: Number(preview.missing_docs ?? 0),
    },
  ]
})

const queueLengthLabel = computed(() => {
  if (typeof props.queueLength === 'number') return String(props.queueLength)
  return '-'
})

const executionPlanSteps = computed(() => {
  const steps: string[] = []
  if (props.processOptions.includeSync) {
    steps.push('Sync document metadata/text baseline from Paperless (insert-only + mark deleted).')
  } else {
    steps.push('Skip sync and use existing local snapshot for missing-work detection.')
  }
  if (props.processOptions.strategy === 'paperless_only') {
    steps.push('Plan missing Paperless baseline tasks (embeddings + suggestions).')
  } else if (props.processOptions.strategy === 'vision_first') {
    steps.push('Prioritize vision OCR pipeline, then downstream embeddings/suggestions.')
  } else if (props.processOptions.strategy === 'max_coverage') {
    steps.push('Plan max-coverage tasks across paperless and vision sources.')
  } else {
    steps.push('Plan balanced missing tasks across baseline + vision where useful.')
  }
  steps.push('Enqueue only missing tasks; no automatic writeback to Paperless is performed.')
  steps.push('Worker executes queued tasks and updates status/timeline progressively.')
  return steps
})

const formatMissingSteps = (value?: unknown) => {
  if (!Array.isArray(value) || value.length === 0) return 'steps: -'
  return `steps: ${value.map((entry) => String(entry)).join(', ')}`
}

const previewDocs = computed<PreviewDocItem[]>(() => {
  const raw = props.processPreview?.preview_docs
  if (!Array.isArray(raw)) return []
  return raw
    .map((entry): PreviewDocItem | null => {
      if (!entry || typeof entry !== 'object') return null
      const obj = entry as Record<string, unknown>
      const docId = Number(obj.doc_id)
      if (!Number.isFinite(docId) || docId <= 0) return null
      const title = typeof obj.title === 'string' && obj.title.trim() ? obj.title : `Document ${docId}`
      const missingSteps = Array.isArray(obj.missing_steps)
        ? obj.missing_steps.map((item) => String(item)).filter(Boolean)
        : []
      const missingTasks = Array.isArray(obj.missing_tasks)
        ? obj.missing_tasks.map((item) => String(item)).filter(Boolean)
        : []
      return {
        doc_id: docId,
        title,
        missing_steps: missingSteps,
        missing_tasks: missingTasks,
      }
    })
    .filter((item): item is PreviewDocItem => item !== null)
})

const _priorityTaskMarkers = [
  'page_notes',
  'summary_hierarchical',
  'suggestions_vision',
  'vision_ocr',
  'embeddings_vision',
]

const priorityScoreForPreviewDoc = (item: PreviewDocItem) => {
  const tasks = Array.isArray(item.missing_tasks) ? item.missing_tasks : []
  const steps = Array.isArray(item.missing_steps) ? item.missing_steps : []
  let score = 0
  for (const task of tasks) {
    const normalized = String(task || '').toLowerCase()
    if (_priorityTaskMarkers.some((marker) => normalized.includes(marker))) score += 2
  }
  if (steps.some((step) => String(step || '').toLowerCase().includes('large'))) score += 3
  return score
}

const isHighPriorityPreviewDoc = (item: PreviewDocItem) => priorityScoreForPreviewDoc(item) >= 3

const prioritizedPreviewDocs = computed(() => {
  return [...previewDocs.value].sort((a, b) => {
    const scoreDiff = priorityScoreForPreviewDoc(b) - priorityScoreForPreviewDoc(a)
    if (scoreDiff !== 0) return scoreDiff
    const taskDiff = (b.missing_tasks?.length || 0) - (a.missing_tasks?.length || 0)
    if (taskDiff !== 0) return taskDiff
    return a.doc_id - b.doc_id
  })
})

const highPriorityPreviewCount = computed(
  () => prioritizedPreviewDocs.value.filter((item) => isHighPriorityPreviewDoc(item)).length,
)

const AUTO_OPEN_COUNTER_THRESHOLD = 10
const showDetailedCounters = ref(false)
const detailsManuallyToggled = ref(false)
const showOnlyNonZeroCounters = ref(true)

const detailedCounters = computed(() => {
  const preview = props.processPreview
  if (!preview) return []
  return [
    { key: 'missing_vision_ocr', label: 'Missing vision OCR', value: Number(preview.missing_vision_ocr ?? 0) },
    { key: 'missing_embeddings_paperless', label: 'Missing embeddings (paperless)', value: Number(preview.missing_embeddings_paperless ?? 0) },
    { key: 'missing_embeddings', label: 'Missing embeddings (target source)', value: Number(preview.missing_embeddings ?? 0) },
    { key: 'missing_embeddings_vision', label: 'Missing vision embeddings', value: Number(preview.missing_embeddings_vision ?? 0) },
    { key: 'missing_page_notes', label: 'Missing page notes', value: Number(preview.missing_page_notes ?? 0) },
    { key: 'missing_summary_hierarchical', label: 'Missing hierarchical summaries', value: Number(preview.missing_summary_hierarchical ?? 0) },
    { key: 'missing_suggestions_paperless', label: 'Missing suggestions (baseline)', value: Number(preview.missing_suggestions_paperless ?? 0) },
    { key: 'missing_suggestions_vision', label: 'Missing suggestions (vision)', value: Number(preview.missing_suggestions_vision ?? 0) },
  ]
})

const visibleDetailedCounters = computed(() => {
  if (!showOnlyNonZeroCounters.value) return detailedCounters.value
  return detailedCounters.value.filter((item) => Number(item.value) > 0)
})

const shouldAutoOpenDetailedCounters = computed(() => {
  const preview = props.processPreview
  if (!preview) return false
  const criticalCounts = [
    Number(preview.missing_vision_ocr ?? 0),
    Number(preview.missing_embeddings ?? 0),
    Number(preview.missing_page_notes ?? 0),
    Number(preview.missing_summary_hierarchical ?? 0),
    Number(preview.missing_suggestions_vision ?? 0),
  ]
  return criticalCounts.some((count) => count >= AUTO_OPEN_COUNTER_THRESHOLD)
})

const syncDetailedCountersVisibility = () => {
  if (detailsManuallyToggled.value) return
  showDetailedCounters.value = shouldAutoOpenDetailedCounters.value
}

const toggleDetailedCounters = () => {
  detailsManuallyToggled.value = true
  showDetailedCounters.value = !showDetailedCounters.value
}

watch(
  () => props.open,
  (isOpen) => {
    if (!isOpen) return
    detailsManuallyToggled.value = false
    syncDetailedCountersVisibility()
  },
)

watch(
  () => props.processPreview,
  () => {
    syncDetailedCountersVisibility()
  },
)

const strategyHint = computed(() => {
  if (props.processOptions.strategy === 'vision_first') {
    return 'Vision first: prioritize vision OCR, vision embeddings, and vision suggestions.'
  }
  if (props.processOptions.strategy === 'paperless_only') {
    return 'Paperless only: skip vision tasks and use baseline OCR only.'
  }
  if (props.processOptions.strategy === 'max_coverage') {
    return 'Max coverage: run both paperless and vision flows (including dual embeddings).'
  }
  return 'Balanced: keep baseline coverage and use vision where available.'
})

const selectedBatchLimit = computed<number | null>(() => {
  const value = props.batchOptions[props.batchIndex]
  if (typeof value === 'number' && Number.isFinite(value) && value > 0) return value
  return null
})

const expectedEnqueueDocs = computed(() => {
  const missingDocs = Number(props.processPreview?.missing_docs ?? 0)
  const limit = selectedBatchLimit.value
  if (!Number.isFinite(missingDocs) || missingDocs <= 0) return 0
  if (limit == null) return missingDocs
  return Math.min(missingDocs, limit)
})

const expectedEnqueueTasksLabel = computed(() => {
  const tasks = Number(props.processPreview?.tasks ?? 0)
  if (!Number.isFinite(tasks) || tasks <= 0) return '0 tasks'
  return `up to ${tasks} tasks`
})

const startDisabledReason = computed(() => {
  if (!props.queueEnabled) return 'Queue disabled'
  if (props.processPreviewLoading) return 'Preview loading'
  if (props.syncing || props.isSyncingNow) return 'Sync running'
  if (expectedEnqueueDocs.value <= 0) return 'No missing work'
  return 'Not ready'
})

const canStartProcessing = computed(() => {
  if (!props.queueEnabled) return false
  if (props.processPreviewLoading) return false
  if (props.syncing || props.isSyncingNow) return false
  return expectedEnqueueDocs.value > 0
})

const strategyLabel = (value: ProcessOptions['strategy']) => {
  if (value === 'vision_first') return 'Vision first'
  if (value === 'paperless_only') return 'Paperless only'
  if (value === 'max_coverage') return 'Max coverage'
  return 'Balanced'
}

const recommendedStrategyInfo = computed<null | { strategy: ProcessOptions['strategy']; reason: string }>(() => {
  const preview = props.processPreview
  if (!preview) return null
  const visionGaps =
    Number(preview.missing_vision_ocr ?? 0) +
    Number(preview.missing_embeddings_vision ?? 0) +
    Number(preview.missing_suggestions_vision ?? 0) +
    Number(preview.missing_page_notes ?? 0) +
    Number(preview.missing_summary_hierarchical ?? 0)
  const paperlessGaps =
    Number(preview.missing_embeddings_paperless ?? 0) +
    Number(preview.missing_suggestions_paperless ?? 0)
  const largeGaps =
    Number(preview.missing_page_notes ?? 0) + Number(preview.missing_summary_hierarchical ?? 0)

  if (largeGaps > 0 || (visionGaps > 0 && paperlessGaps > 0)) {
    return { strategy: 'max_coverage', reason: 'large-doc or mixed source gaps detected' }
  }
  if (visionGaps > 0) {
    return { strategy: 'vision_first', reason: 'vision pipeline gaps dominate' }
  }
  if (paperlessGaps > 0) {
    return { strategy: 'balanced', reason: 'baseline tasks remain' }
  }
  return { strategy: 'balanced', reason: 'already mostly covered' }
})

const applyRecommendedStrategy = () => {
  const next = recommendedStrategyInfo.value?.strategy
  if (!next) return
  props.processOptions.strategy = next
}

const strategyWarnings = computed(() => {
  const preview = props.processPreview
  if (!preview) return []
  const warnings: string[] = []
  if (props.processOptions.strategy === 'paperless_only') {
    const visionGaps =
      Number(preview.missing_vision_ocr ?? 0) +
      Number(preview.missing_embeddings_vision ?? 0) +
      Number(preview.missing_suggestions_vision ?? 0) +
      Number(preview.missing_page_notes ?? 0) +
      Number(preview.missing_summary_hierarchical ?? 0)
    if (visionGaps > 0) {
      warnings.push(
        `Selected strategy may leave ${visionGaps} vision-related gaps unresolved (switch to Balanced, Vision first, or Max coverage to include them).`,
      )
    }
  }
  if (props.processOptions.strategy === 'vision_first') {
    const baselineGaps =
      Number(preview.missing_embeddings_paperless ?? 0) +
      Number(preview.missing_suggestions_paperless ?? 0)
    if (baselineGaps > 0) {
      warnings.push(
        `Baseline paperless tasks still missing: ${baselineGaps}. Consider Balanced or Max coverage if baseline parity is required.`,
      )
    }
  }
  return warnings
})
</script>
