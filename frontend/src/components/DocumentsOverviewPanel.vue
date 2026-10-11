<template>
  <div class="flex w-full flex-col gap-3 xl:w-auto xl:flex-row xl:items-start">
    <div
      class="flex w-full flex-wrap items-center gap-x-4 gap-y-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600 shadow-sm xl:w-auto dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
      data-testid="overview-stats"
    >
      <span title="Documents synced from Paperless (deleted ones stay in Cortex but are not listed)">
        <span class="text-slate-500">Synced</span>
        <span class="ml-1 font-semibold text-slate-900 dark:text-slate-100">{{ stats.total }}</span>
      </span>
      <span>
        <span class="text-slate-500">Queued</span>
        <span class="ml-1 font-semibold text-indigo-600">{{ queuedCount }}</span>
      </span>
      <span title="Documents with embeddings">
        <span class="text-slate-500">Embeddings</span>
        <span class="ml-1 font-semibold text-emerald-600">{{ stats.embeddings }}</span>
      </span>
      <span>
        <span class="text-slate-500">Vision OCR</span>
        <span class="ml-1 font-semibold text-emerald-600">{{ stats.vision }}</span>
      </span>
      <span>
        <span class="text-slate-500">Suggestions</span>
        <span class="ml-1 font-semibold text-emerald-600">{{ stats.suggestions }}</span>
      </span>
      <span>
        <span class="text-slate-500">Fully processed</span>
        <span class="ml-1 font-semibold text-emerald-700 dark:text-emerald-400">{{
          stats.fully_processed
        }}</span>
      </span>
      <span>
        <span class="text-slate-500">Pending</span>
        <span class="ml-1 font-semibold text-amber-600">{{ stats.unprocessed }}</span>
      </span>
    </div>
    <div
      v-if="isProcessing"
      class="flex w-full items-start gap-3 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600 shadow-sm xl:w-auto dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
    >
      <Loader2 class="h-4 w-4 animate-spin text-indigo-500" />
      <div class="min-w-0 space-y-0.5">
        <div v-if="syncStatus.status === 'running'">
          Sync {{ syncStatus.processed }} / {{ syncStatus.total }} ({{ progressPercent }}%) -
          ETA {{ etaText }}
        </div>
        <div v-if="embedStatus.status === 'running' || hasQueuedWork">
          {{ embedLabel }} {{ processingProcessed }} / {{ processingTotal }} ({{ processingPercent }}%) -
          ETA {{ processingEtaText }}
        </div>
        <div
          v-if="hasQueuedWork && lastRunText !== '--'"
          class="text-xs text-slate-500 dark:text-slate-400"
        >
          Last run: {{ lastRunText }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Loader2 } from 'lucide-vue-next'
import type { DocumentStats, EmbedStatus, SyncStatus } from '../services/documents'

defineProps<{
  stats: DocumentStats
  queuedCount: number
  isProcessing: boolean
  syncStatus: SyncStatus
  embedStatus: EmbedStatus
  hasQueuedWork: boolean
  progressPercent: number
  etaText: string
  embedLabel: string
  processingProcessed: number
  processingTotal: number
  processingPercent: number
  processingEtaText: string
  lastRunText: string
}>()
</script>
