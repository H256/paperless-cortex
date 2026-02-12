<template>
  <div class="flex items-center gap-3">
    <div
      class="grid grid-cols-4 gap-x-3 gap-y-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600 shadow-sm dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
    >
      <div class="text-slate-500">Synced</div>
      <div class="font-semibold text-slate-900 dark:text-slate-100">{{ stats.total }}</div>
      <div class="text-slate-500">Queued</div>
      <div class="font-semibold text-indigo-600">{{ queuedCount }}</div>

      <div class="text-slate-500">Embeddings</div>
      <div class="font-semibold text-emerald-600">{{ stats.embeddings }}</div>
      <div class="text-slate-500">Vision OCR</div>
      <div class="font-semibold text-emerald-600">{{ stats.vision }}</div>

      <div class="text-slate-500">Suggestions</div>
      <div class="font-semibold text-emerald-600">{{ stats.suggestions }}</div>
      <div class="text-slate-500">Fully processed</div>
      <div class="font-semibold text-emerald-700 dark:text-emerald-400">
        {{ stats.fully_processed }}
      </div>

      <div class="text-slate-500">Pending</div>
      <div class="font-semibold text-amber-600">{{ stats.unprocessed }}</div>
      <div class="text-slate-500">Processed*</div>
      <div class="font-semibold text-emerald-600">{{ stats.processed }}</div>
    </div>
    <div
      v-if="isProcessing"
      class="flex items-center gap-3 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600 shadow-sm dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
    >
      <Loader2 class="h-4 w-4 animate-spin text-indigo-500" />
      <div class="space-y-0.5">
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
