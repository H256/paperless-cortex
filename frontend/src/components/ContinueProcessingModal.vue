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
        <div
          class="rounded-lg border border-slate-200 bg-white p-3 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
        >
          Missing vision OCR:
          <strong class="text-slate-900 dark:text-slate-100">{{
            processPreview?.missing_vision_ocr ?? 0
          }}</strong>
        </div>
        <div
          class="rounded-lg border border-slate-200 bg-white p-3 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
        >
          Missing embeddings (paperless):
          <strong class="text-slate-900 dark:text-slate-100">{{
            processPreview?.missing_embeddings_paperless ?? 0
          }}</strong>
        </div>
        <div
          class="rounded-lg border border-slate-200 bg-white p-3 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
        >
          Missing embeddings (target source):
          <strong class="text-slate-900 dark:text-slate-100">{{
            processPreview?.missing_embeddings ?? 0
          }}</strong>
        </div>
        <div
          class="rounded-lg border border-slate-200 bg-white p-3 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
        >
          Missing vision embeddings:
          <strong class="text-slate-900 dark:text-slate-100">{{
            processPreview?.missing_embeddings_vision ?? 0
          }}</strong>
        </div>
        <div
          class="rounded-lg border border-slate-200 bg-white p-3 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
        >
          Missing page notes:
          <strong class="text-slate-900 dark:text-slate-100">{{
            processPreview?.missing_page_notes ?? 0
          }}</strong>
        </div>
        <div
          class="rounded-lg border border-slate-200 bg-white p-3 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
        >
          Missing hierarchical summaries:
          <strong class="text-slate-900 dark:text-slate-100">{{
            processPreview?.missing_summary_hierarchical ?? 0
          }}</strong>
        </div>
        <div
          class="rounded-lg border border-slate-200 bg-white p-3 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
        >
          Missing suggestions (baseline):
          <strong class="text-slate-900 dark:text-slate-100">{{
            processPreview?.missing_suggestions_paperless ?? 0
          }}</strong>
        </div>
        <div
          class="rounded-lg border border-slate-200 bg-white p-3 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
        >
          Missing suggestions (vision):
          <strong class="text-slate-900 dark:text-slate-100">{{
            processPreview?.missing_suggestions_vision ?? 0
          }}</strong>
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
        v-if="!processPreviewLoading && previewDocs.length"
        class="mt-4 rounded-lg border border-slate-200 bg-white p-4 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
      >
        <div class="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          Sample Documents With Gaps
        </div>
        <div class="mt-2 max-h-40 space-y-1 overflow-auto pr-1">
          <div
            v-for="item in previewDocs"
            :key="item.doc_id"
            class="flex items-start justify-between gap-2 rounded-md border border-slate-200 bg-slate-50 px-2 py-1.5 dark:border-slate-700 dark:bg-slate-800"
          >
            <div class="min-w-0">
              <div class="truncate font-semibold text-slate-800 dark:text-slate-100">
                #{{ item.doc_id }} {{ item.title || 'Untitled' }}
              </div>
              <div class="truncate text-[11px] text-slate-500 dark:text-slate-400">
                {{ (item.missing_tasks || []).join(', ') || '-' }}
              </div>
            </div>
            <div class="shrink-0 text-[11px] font-semibold text-amber-600 dark:text-amber-300">
              {{ formatMissingSteps(item.missing_steps) }}
            </div>
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
          <label
            class="flex items-center gap-2 text-xs font-medium text-slate-700 dark:text-slate-200"
          >
            <input
              type="checkbox"
              v-model="processOptions.includeVisionOcr"
              class="h-4 w-4 rounded border-slate-300 text-indigo-600"
            />
            Vision OCR
          </label>
          <label
            class="flex items-center gap-2 text-xs font-medium text-slate-700 dark:text-slate-200"
          >
            <input
              type="checkbox"
              v-model="processOptions.includeEmbeddingsPaperless"
              class="h-4 w-4 rounded border-slate-300 text-indigo-600"
            />
            Embeddings (paperless)
          </label>
          <label
            class="flex items-center gap-2 text-xs font-medium text-slate-700 dark:text-slate-200"
          >
            <input
              type="checkbox"
              v-model="processOptions.includeEmbeddingsVision"
              class="h-4 w-4 rounded border-slate-300 text-indigo-600"
            />
            Embeddings (vision)
          </label>
          <label class="flex flex-col gap-1 text-xs font-medium text-slate-700 dark:text-slate-200 sm:col-span-2">
            Embedding mode
            <select
              v-model="processOptions.embeddingsMode"
              class="rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            >
              <option value="auto">Auto (prefer vision)</option>
              <option value="vision">Vision only</option>
              <option value="paperless">Paperless only</option>
              <option value="both">Both sources</option>
            </select>
          </label>
          <div class="text-[11px] text-slate-400 dark:text-slate-500 sm:col-span-2">
            Auto prefers vision when available. "Both sources" stores paperless and vision embeddings side-by-side.
          </div>
          <label
            class="flex items-center gap-2 text-xs font-medium text-slate-700 dark:text-slate-200"
          >
            <input
              type="checkbox"
              v-model="processOptions.includePageNotes"
              class="h-4 w-4 rounded border-slate-300 text-indigo-600"
            />
            Page notes
          </label>
          <label
            class="flex items-center gap-2 text-xs font-medium text-slate-700 dark:text-slate-200"
          >
            <input
              type="checkbox"
              v-model="processOptions.includeHierarchicalSummary"
              class="h-4 w-4 rounded border-slate-300 text-indigo-600"
            />
            Hierarchical summary
          </label>
          <label
            class="flex items-center gap-2 text-xs font-medium text-slate-700 dark:text-slate-200"
          >
            <input
              type="checkbox"
              v-model="processOptions.includeSuggestionsPaperless"
              class="h-4 w-4 rounded border-slate-300 text-indigo-600"
            />
            Suggestions (baseline)
          </label>
          <label
            class="flex items-center gap-2 text-xs font-medium text-slate-700 dark:text-slate-200"
          >
            <input
              type="checkbox"
              v-model="processOptions.includeSuggestionsVision"
              class="h-4 w-4 rounded border-slate-300 text-indigo-600"
            />
            Suggestions (vision)
          </label>
        </div>
      </div>

      <div class="mt-6 flex flex-wrap items-center justify-end gap-3">
        <button
          v-if="processStartResult"
          class="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
          @click="$emit('close')"
        >
          Close
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
                isSyncingNow,
            }"
            :disabled="
              processPreviewLoading || processStartLoading || syncing || isSyncingNow
            "
            @click="$emit('start')"
          >
            <span v-if="processStartLoading" class="inline-flex items-center gap-2">
              <Loader2 class="h-4 w-4 animate-spin" />
              Enqueuing...
            </span>
            <span v-else-if="isSyncingNow">Syncing...</span>
            <span v-else>Start processing</span>
          </button>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Loader2 } from 'lucide-vue-next'
import type { ProcessMissingResponse, SyncStatusResponse } from '@/api/generated/model'

type ProcessOptions = {
  includeSync: boolean
  includeVisionOcr: boolean
  includeEmbeddingsPaperless: boolean
  includeEmbeddingsVision: boolean
  embeddingsMode: 'auto' | 'paperless' | 'vision' | 'both'
  includePageNotes: boolean
  includeHierarchicalSummary: boolean
  includeSuggestionsPaperless: boolean
  includeSuggestionsVision: boolean
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
}>()

const emit = defineEmits<{
  close: []
  start: []
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
</script>
