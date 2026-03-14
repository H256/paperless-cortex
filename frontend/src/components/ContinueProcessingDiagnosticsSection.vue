<template>
  <template v-if="showDiagnostics && !processPreviewLoading && processPreview">
    <div class="mt-4 rounded-lg border border-slate-200 bg-white p-4 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300">
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

    <div class="mt-4 rounded-lg border border-slate-200 bg-white p-4 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300">
      <div class="flex items-center justify-between gap-2">
        <div class="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          Detailed Missing Counters
        </div>
        <button
          class="rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
          @click="$emit('toggle-detailed-counters')"
        >
          {{ showDetailedCounters ? 'Hide details' : 'Show details' }}
        </button>
      </div>
      <label
        v-if="showDetailedCounters"
        class="mt-2 inline-flex items-center gap-1.5 text-[11px] text-slate-500 dark:text-slate-400"
      >
        <input
          :checked="showOnlyNonZeroCounters"
          type="checkbox"
          class="h-3.5 w-3.5"
          @change="$emit('update:show-only-non-zero', ($event.target as HTMLInputElement).checked)"
        />
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
      v-if="previewDocs.length"
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
      <div class="mt-2 max-h-32 space-y-1 overflow-auto pr-1 sm:max-h-40">
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

    <div class="mt-4 rounded-lg border border-slate-200 bg-white p-4 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300">
      <div class="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
        What Happens Next
      </div>
      <ol class="mt-2 list-decimal space-y-1.5 pl-4">
        <li v-for="step in executionPlanSteps" :key="step">
          {{ step }}
        </li>
      </ol>
      <div v-if="executionScopeItems.length" class="mt-3 grid gap-2 sm:grid-cols-2">
        <div
          v-for="item in executionScopeItems"
          :key="item.key"
          class="flex items-center justify-between rounded-md border px-2 py-1.5"
          :class="item.included
            ? 'border-emerald-200 bg-emerald-50 dark:border-emerald-900/50 dark:bg-emerald-950/20'
            : 'border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-800'"
        >
          <span>{{ item.label }}</span>
          <span
            class="text-[11px] font-semibold"
            :class="item.included
              ? 'text-emerald-700 dark:text-emerald-300'
              : 'text-slate-500 dark:text-slate-400'"
          >
            {{ item.included ? 'included' : 'excluded' }}
          </span>
        </div>
      </div>
    </div>

    <div class="mt-4 rounded-lg border border-slate-200 bg-white p-4 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300">
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
  </template>
</template>

<script setup lang="ts">
import type { ProcessMissingResponse } from '@/api/generated/model'
import { isHighPriorityPreviewDoc, type PreviewDocItem } from '../utils/continueProcessingPanel'

defineProps<{
  showDiagnostics: boolean
  processPreviewLoading: boolean
  processPreview: ProcessMissingResponse | null
  coverageItems: { key: string; label: string; missing: number }[]
  showDetailedCounters: boolean
  showOnlyNonZeroCounters: boolean
  visibleDetailedCounters: { key: string; label: string; value: number }[]
  previewDocs: PreviewDocItem[]
  prioritizedPreviewDocs: PreviewDocItem[]
  highPriorityPreviewCount: number
  executionPlanSteps: string[]
  executionScopeItems: { key: string; label: string; included: boolean }[]
  queueEnabled: boolean
  queueLengthLabel: string
  processingActive: boolean
}>()

defineEmits<{
  'toggle-detailed-counters': []
  'update:show-only-non-zero': [value: boolean]
  'open-doc': [docId: number]
}>()

const formatMissingSteps = (value?: unknown) => {
  if (!Array.isArray(value) || value.length === 0) return 'steps: -'
  return `steps: ${value.map((entry) => String(entry)).join(', ')}`
}
</script>
