<template>
  <div class="space-y-4">
    <div class="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
      <div>
        <h2 class="text-2xl font-semibold tracking-tight">Documents</h2>
        <p class="text-sm text-slate-500">
          Manage ingestion, embedding, and review analysis status.
        </p>
        <p
          class="mt-1 flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400"
        >
          Showing {{ visibleCount }} of {{ totalCount }} synced documents
          <template v-if="searchLabel">
            for "{{ searchLabel }}"
          </template>
          <Info
            class="h-3.5 w-3.5 shrink-0 text-slate-400 dark:text-slate-500"
            title="Showing is the number of documents currently listed after your filters; synced is the total in Paperless. Documents deleted in Paperless stay in Cortex but are not listed here, so this number can be lower than the synced total."
          />
        </p>
      </div>
      <DocumentsOverviewPanel
        :stats="stats"
        :queued-count="queuedCount"
        :is-processing="isProcessing"
        :sync-status="syncStatus"
        :embed-status="embedStatus"
        :has-queued-work="hasQueuedWork"
        :progress-percent="progressPercent"
        :eta-text="etaText"
        :embed-label="embedLabel"
        :processing-processed="processingProcessed"
        :processing-total="processingTotal"
        :processing-percent="processingPercent"
        :processing-eta-text="processingEtaText"
        :last-run-text="lastRunText"
      />
    </div>

    <DocumentsProcessingToolbar
      :continue-processing-running="false"
      :processing-kickoff-pending="false"
      :is-processing="isProcessing"
      :show-cancel="showCancel"
      @open-preview="$emit('open-preview')"
      @cancel-processing="$emit('cancel-processing')"
      @open-queue="$emit('open-queue')"
      @open-logs="$emit('open-logs')"
    />
  </div>
</template>

<script setup lang="ts">
import { Info } from 'lucide-vue-next'
import type { DocumentStats, EmbedStatus, SyncStatus } from '../services/documents'
import DocumentsOverviewPanel from './DocumentsOverviewPanel.vue'
import DocumentsProcessingToolbar from './DocumentsProcessingToolbar.vue'

defineProps<{
  visibleCount: number
  totalCount: number
  searchLabel: string
  stats: DocumentStats
  queuedCount: number
  isProcessing: boolean
  syncStatus: SyncStatus
  embedStatus: EmbedStatus
  hasQueuedWork: boolean
  showCancel: boolean
  progressPercent: number
  etaText: string
  embedLabel: string
  processingProcessed: number
  processingTotal: number
  processingPercent: number
  processingEtaText: string
  lastRunText: string
}>()

defineEmits<{
  'open-preview': []
  'cancel-processing': []
  'open-queue': []
  'open-logs': []
}>()
</script>
