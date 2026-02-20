<template>
  <section class="space-y-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h3 class="text-lg font-semibold text-slate-900 dark:text-slate-100">Document operations</h3>
        <p class="text-xs text-slate-500 dark:text-slate-400">
          Trigger single processing steps or fully reset and rebuild this document.
        </p>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <button
          class="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
          :disabled="docOpsLoading || pipelineStatusLoading || continuePipelineLoading"
          title="Checks missing processing steps for this document and enqueues only those tasks."
          @click="$emit('continue-pipeline')"
        >
          {{ continuePipelineLoading ? 'Checking + enqueueing...' : 'Continue missing processing' }}
        </button>
        <button
          class="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
          @click="$emit('open-queue')"
        >
          Queue
        </button>
        <button
          class="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
          @click="$emit('open-logs')"
        >
          Logs
        </button>
      </div>
    </div>

    <div
      v-if="continuePipelineLoading || continueQueuedWaiting"
      class="rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-2 text-xs text-indigo-700 dark:border-indigo-900/50 dark:bg-indigo-950/30 dark:text-indigo-200"
    >
      <span v-if="continuePipelineLoading">Checking missing steps and enqueueing tasks...</span>
      <span v-else-if="continueQueuedWaiting && !hasActiveTaskRuns">
        Tasks enqueued. Waiting for worker pickup...
      </span>
      <span v-else>
        Worker picked up tasks. Progress is visible in timeline and fan-out below.
      </span>
    </div>

    <div class="rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-slate-800 dark:bg-slate-800">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div class="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-300">
          Processing status
        </div>
        <div class="text-xs text-slate-500 dark:text-slate-300">
          Done {{ processingDoneCount }} / {{ processingRequiredCount }} required
        </div>
      </div>
      <div class="mt-1 text-xs text-slate-500 dark:text-slate-300">
        Preferred source: {{ toTitle(pipelinePreferredSource) }}
      </div>
      <div class="mt-1 text-xs" :class="isLargeDocumentMode ? 'text-indigo-600 dark:text-indigo-300' : 'text-slate-500 dark:text-slate-300'">
        {{ largeDocumentHint }}
      </div>
      <div v-if="pipelineStatusLoading" class="mt-2 text-xs text-slate-500 dark:text-slate-300">
        Loading pipeline status...
      </div>
      <div v-else-if="pipelineStatusError" class="mt-2 text-xs text-rose-600 dark:text-rose-300">
        {{ pipelineStatusError }}
      </div>
      <div v-else-if="!processingStatusItems.length" class="mt-2 text-xs text-slate-500 dark:text-slate-300">
        No processing status available.
      </div>
      <div class="mt-2 grid gap-2 md:grid-cols-2">
        <div
          v-for="item in processingStatusItems"
          :key="item.label"
          class="flex items-center justify-between rounded-md border border-slate-200 bg-white px-2 py-1.5 text-xs dark:border-slate-700 dark:bg-slate-900"
        >
          <span class="text-slate-700 dark:text-slate-200">{{ item.label }}</span>
          <span
            class="inline-flex items-center gap-1 font-semibold"
            :class="processingBadgeClass(item.state)"
            :title="item.detail"
          >
            <CheckCircle v-if="item.state === 'done'" class="h-3.5 w-3.5" />
            <AlertTriangle v-else-if="item.state === 'missing'" class="h-3.5 w-3.5" />
            <MinusCircle v-else class="h-3.5 w-3.5" />
            {{ processingStateLabel(item.state) }}
          </span>
        </div>
      </div>
    </div>

    <div class="rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-slate-800 dark:bg-slate-800">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div class="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-300">
          Downstream fan-out
        </div>
        <button
          class="rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
          :disabled="pipelineFanoutLoading"
          @click="$emit('reload-fanout')"
        >
          {{ pipelineFanoutLoading ? 'Loading...' : 'Reload fan-out' }}
        </button>
      </div>
      <div v-if="pipelineFanoutError" class="mt-2 text-xs text-rose-600 dark:text-rose-300">
        {{ pipelineFanoutError }}
      </div>
      <div v-else-if="!pipelineFanoutItems.length" class="mt-2 text-xs text-slate-500 dark:text-slate-300">
        No downstream fan-out tasks available.
      </div>
      <template v-else>
        <div class="mt-2 space-y-2 md:hidden">
          <article
            v-for="item in pipelineFanoutItems"
            :key="`fanout-mobile-${item.order}-${item.task}-${item.source || ''}`"
            class="rounded-md border border-slate-200 bg-white p-2 text-xs dark:border-slate-700 dark:bg-slate-900"
          >
            <div class="flex items-center justify-between gap-2">
              <div class="font-semibold">{{ item.order }}. {{ item.task }}</div>
              <div class="font-semibold" :class="fanoutStatusClass(item.status)">{{ item.status }}</div>
            </div>
            <div v-if="item.source" class="mt-1 text-slate-500 dark:text-slate-400">Source: {{ item.source }}</div>
            <div class="mt-1 text-slate-500 dark:text-slate-400">
              Last run: {{ toRelativeTime(item.last_started_at) }}
              <span v-if="item.checkpoint" class="ml-1">· {{ checkpointLabel(item.checkpoint) }}</span>
            </div>
            <div class="mt-1 text-rose-600 dark:text-rose-300">Error: {{ item.error_type || '-' }}</div>
          </article>
        </div>
        <div class="mt-2 hidden overflow-x-auto md:block">
          <table class="min-w-full text-xs">
            <thead class="text-left text-slate-500 dark:text-slate-400">
              <tr>
                <th class="px-2 py-1">#</th>
                <th class="px-2 py-1">Task</th>
                <th class="px-2 py-1">Status</th>
                <th class="px-2 py-1">Last run</th>
                <th class="px-2 py-1">Error</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in pipelineFanoutItems" :key="`${item.order}-${item.task}-${item.source || ''}`" class="border-t border-slate-100 dark:border-slate-700">
                <td class="px-2 py-1.5">{{ item.order }}</td>
                <td class="px-2 py-1.5">{{ item.task }}<span v-if="item.source" class="text-slate-400"> ({{ item.source }})</span></td>
                <td class="px-2 py-1.5" :class="fanoutStatusClass(item.status)">{{ item.status }}</td>
                <td class="px-2 py-1.5" :title="toDateTime(item.last_started_at)">
                  {{ toRelativeTime(item.last_started_at) }}
                  <span v-if="item.checkpoint" class="ml-1 text-slate-400">· {{ checkpointLabel(item.checkpoint) }}</span>
                </td>
                <td class="px-2 py-1.5">{{ item.error_type || '-' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </div>

    <div class="rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-slate-800 dark:bg-slate-800">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div class="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-300">
          Processing timeline
        </div>
        <div class="flex w-full flex-wrap items-end gap-2 sm:w-auto sm:justify-end">
          <label class="flex flex-col text-[11px] font-medium text-slate-500 dark:text-slate-300">
            Status
            <select
              :value="timelineStatusFilter"
              class="mt-1 h-8 w-24 rounded-md border border-slate-200 bg-white px-1.5 text-xs text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
              @change="$emit('update:timeline-status-filter', String(($event.target as HTMLSelectElement).value))"
            >
              <option value="">all</option>
              <option value="running">running</option>
              <option value="retrying">retrying</option>
              <option value="failed">failed</option>
              <option value="done">done</option>
            </select>
          </label>
          <label class="flex flex-col text-[11px] font-medium text-slate-500 dark:text-slate-300">
            Search
            <input
              :value="timelineQueryFilter"
              type="text"
              placeholder="task/error..."
              class="mt-1 h-8 w-40 rounded-md border border-slate-200 bg-white px-1.5 text-xs text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
              @input="$emit('update:timeline-query-filter', String(($event.target as HTMLInputElement).value))"
            />
          </label>
          <button
            class="rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
            :disabled="taskRunsLoading"
            @click="$emit('refresh-task-runs')"
          >
            {{ taskRunsLoading ? 'Loading...' : 'Reload timeline' }}
          </button>
        </div>
      </div>
      <div v-if="taskRunsError" class="mt-2 text-xs text-rose-600 dark:text-rose-300">
        {{ taskRunsError }}
      </div>
      <div v-else-if="!taskRuns.length" class="mt-2 text-xs text-slate-500 dark:text-slate-300">
        No task runs for this document yet.
      </div>
      <template v-else>
        <div class="mt-2 space-y-2 md:hidden">
          <article
            v-for="run in taskRuns"
            :key="`taskrun-mobile-${run.id}`"
            class="rounded-md border border-slate-200 bg-white p-2 text-xs dark:border-slate-700 dark:bg-slate-900"
          >
            <div class="flex items-center justify-between gap-2">
              <div class="font-semibold">{{ run.task }}</div>
              <div class="font-semibold" :class="run.status === 'failed' ? 'text-rose-700 dark:text-rose-300' : 'text-slate-700 dark:text-slate-200'">
                {{ run.status }}
              </div>
            </div>
            <div class="mt-1 text-slate-500 dark:text-slate-400">
              Started: {{ toRelativeTime(run.started_at) }} · Attempt {{ run.attempt ?? 1 }}
            </div>
            <div class="mt-1 text-slate-500 dark:text-slate-400">
              Checkpoint: {{ checkpointLabel(run.checkpoint) }}
            </div>
            <div v-if="embeddingTelemetryLabel(run.checkpoint)" class="mt-1 text-[11px] text-amber-600 dark:text-amber-300">
              {{ embeddingTelemetryLabel(run.checkpoint) }}
            </div>
            <div class="mt-1 text-rose-600 dark:text-rose-300">
              {{ run.error_type || '-' }}
            </div>
            <div v-if="run.error_message" class="mt-1 text-[11px] text-slate-500 dark:text-slate-400" :title="run.error_message">
              {{ compactErrorMessage(run.error_message) }}
            </div>
            <div class="mt-2 flex flex-wrap items-center gap-1.5">
              <button
                v-if="run.status === 'failed'"
                class="rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
                :disabled="docOpsLoading"
                @click="$emit('retry-task-run', run)"
              >
                Retry
              </button>
              <button
                v-if="run.error_message"
                class="rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
                :disabled="docOpsLoading"
                @click="$emit('copy-run-error', run.error_message)"
              >
                Copy error
              </button>
            </div>
          </article>
        </div>
        <div class="mt-2 hidden overflow-x-auto md:block">
          <table class="min-w-full text-xs">
            <thead class="text-left text-slate-500 dark:text-slate-400">
              <tr>
                <th class="px-2 py-1">Started</th>
                <th class="px-2 py-1">Task</th>
                <th class="px-2 py-1">Status</th>
                <th class="px-2 py-1">Attempt</th>
                <th class="px-2 py-1">Checkpoint</th>
                <th class="px-2 py-1">Error</th>
                <th class="px-2 py-1">Action</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="run in taskRuns" :key="run.id" class="border-t border-slate-100 dark:border-slate-700">
                <td class="px-2 py-1.5" :title="toDateTime(run.started_at)">{{ toRelativeTime(run.started_at) }}</td>
                <td class="px-2 py-1.5">{{ run.task }}</td>
                <td class="px-2 py-1.5" :class="run.status === 'failed' ? 'text-rose-700 dark:text-rose-300 font-semibold' : 'text-slate-700 dark:text-slate-200'">
                  {{ run.status }}
                </td>
                <td class="px-2 py-1.5">{{ run.attempt ?? 1 }}</td>
                <td class="px-2 py-1.5">
                  <div>{{ checkpointLabel(run.checkpoint) }}</div>
                  <div v-if="embeddingTelemetryLabel(run.checkpoint)" class="text-[11px] text-amber-600 dark:text-amber-300">
                    {{ embeddingTelemetryLabel(run.checkpoint) }}
                  </div>
                </td>
                <td class="px-2 py-1.5">
                  <div>{{ run.error_type || '-' }}</div>
                  <div v-if="run.error_message" class="text-[11px] text-slate-500 dark:text-slate-400" :title="run.error_message">
                    {{ compactErrorMessage(run.error_message) }}
                  </div>
                </td>
                <td class="px-2 py-1.5">
                  <div class="flex items-center gap-1.5">
                    <button
                      v-if="run.status === 'failed'"
                      class="rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
                      :disabled="docOpsLoading"
                      @click="$emit('retry-task-run', run)"
                    >
                      Retry
                    </button>
                    <button
                      v-if="run.error_message"
                      class="rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
                      :disabled="docOpsLoading"
                      @click="$emit('copy-run-error', run.error_message)"
                    >
                      Copy error
                    </button>
                    <span v-if="run.status !== 'failed' && !run.error_message" class="text-slate-400 dark:text-slate-500">-</span>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </div>

    <div class="rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-slate-800 dark:bg-slate-800">
      <label class="inline-flex items-center gap-2 text-xs text-slate-500 dark:text-slate-300">
        <input
          type="checkbox"
          :checked="docCleanupClearFirst"
          @change="$emit('update:doc-cleanup-clear-first', ($event.target as HTMLInputElement).checked)"
        />
        Clear clean fields first
      </label>
      <div class="mt-2">
        <button
          class="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
          :disabled="docOpsLoading"
          title="Cleans stored page texts (e.g., line wraps or HTML noise) and updates clean fields."
          @click="$emit('run-doc-cleanup')"
        >
          Cleanup page texts (this doc)
        </button>
      </div>
    </div>

    <div class="grid gap-2 md:grid-cols-2">
      <button
        v-for="action in operationActions"
        :key="action.task"
        class="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
        :disabled="docOpsLoading"
        :title="action.tooltip"
        @click="$emit('enqueue-doc-task', action)"
      >
        {{ action.label }}
      </button>
    </div>

    <div class="rounded-lg border border-rose-200 bg-rose-50 p-3 dark:border-rose-900/50 dark:bg-rose-950/40">
      <button
        class="rounded-lg bg-rose-600 px-3 py-2 text-xs font-semibold text-white hover:bg-rose-500"
        :disabled="docOpsLoading"
        title="Deletes local intelligence data for this document, resyncs from Paperless, and enqueues processing."
        @click="$emit('open-reset-confirm')"
      >
        Reset document + sync + full reprocess
      </button>
      <p class="mt-2 text-xs text-rose-700 dark:text-rose-200">
        Deletes local intelligence for this document, syncs from Paperless, then enqueues full processing.
      </p>
    </div>

    <div v-if="docOpsMessage" class="text-xs text-slate-500 dark:text-slate-300">
      {{ docOpsMessage }}
    </div>
  </section>
</template>

<script setup lang="ts">
import { AlertTriangle, CheckCircle, MinusCircle } from 'lucide-vue-next'

type ProcessingStatusItem = {
  label: string
  state: 'done' | 'missing' | 'na'
  detail: string
}

type PipelineFanoutItem = {
  order?: number
  task?: string | null
  source?: string | null
  status?: string | null
  last_started_at?: string | null
  checkpoint?: unknown
  error_type?: string | null
}

type TimelineTaskRun = {
  id: string | number
  task: string
  status: string
  started_at?: string | null
  attempt?: number | null
  checkpoint?: unknown
  error_type?: string | null
  error_message?: string | null
  source?: string | null
}

type OperationAction = {
  task: string
  label: string
  tooltip: string
}

defineProps<{
  continuePipelineLoading: boolean
  continueQueuedWaiting: boolean
  hasActiveTaskRuns: boolean
  docOpsLoading: boolean
  pipelineStatusLoading: boolean
  pipelineStatusError: string
  processingDoneCount: number
  processingRequiredCount: number
  pipelinePreferredSource: string
  isLargeDocumentMode: boolean
  largeDocumentHint: string
  processingStatusItems: ProcessingStatusItem[]
  pipelineFanoutLoading: boolean
  pipelineFanoutError: string
  pipelineFanoutItems: PipelineFanoutItem[]
  timelineStatusFilter: string
  timelineQueryFilter: string
  taskRunsLoading: boolean
  taskRunsError: string
  taskRuns: TimelineTaskRun[]
  docCleanupClearFirst: boolean
  docOpsMessage: string
  operationActions: OperationAction[]
  toTitle: (value: string | null | undefined) => string
  processingBadgeClass: (state: 'done' | 'missing' | 'na') => string
  processingStateLabel: (state: 'done' | 'missing' | 'na') => string
  fanoutStatusClass: (status: string | null | undefined) => string
  toRelativeTime: (value?: string | null) => string
  toDateTime: (value?: string | null) => string
  checkpointLabel: (value?: unknown) => string
  embeddingTelemetryLabel: (checkpoint?: unknown) => string
  compactErrorMessage: (message?: string | null) => string
}>()

defineEmits<{
  'continue-pipeline': []
  'open-queue': []
  'open-logs': []
  'reload-fanout': []
  'update:timeline-status-filter': [value: string]
  'update:timeline-query-filter': [value: string]
  'refresh-task-runs': []
  'retry-task-run': [run: TimelineTaskRun]
  'copy-run-error': [message?: string | null]
  'update:doc-cleanup-clear-first': [value: boolean]
  'run-doc-cleanup': []
  'enqueue-doc-task': [action: OperationAction]
  'open-reset-confirm': []
}>()
</script>
