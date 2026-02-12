<template>
  <div
    v-if="open"
    class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4"
  >
    <ContinueProcessingPanel
      :sync-status="syncStatus"
      :progress-percent="progressPercent"
      :eta-text="etaText"
      :process-preview-loading="processPreviewLoading"
      :process-preview="processPreview"
      :process-options="processOptions"
      :batch-index="batchIndex"
      :batch-options="batchOptions"
      :batch-label="batchLabel"
      :process-start-result="processStartResult"
      :process-start-loading="processStartLoading"
      :syncing="syncing"
      :is-syncing-now="isSyncingNow"
      :queue-enabled="queueEnabled"
      :queue-length="queueLength"
      :processing-active="processingActive"
      @close="$emit('close')"
      @start="$emit('start')"
      @open-doc="$emit('open-doc', $event)"
      @open-queue="$emit('open-queue')"
      @open-logs="$emit('open-logs')"
      @update:batch-index="$emit('update:batchIndex', $event)"
    />
  </div>
</template>

<script setup lang="ts">
import type { ProcessMissingResponse, SyncStatusResponse } from '@/api/generated/model'
import ContinueProcessingPanel from './ContinueProcessingPanel.vue'

type ProcessOptions = {
  includeSync: boolean
  strategy: 'balanced' | 'paperless_only' | 'vision_first' | 'max_coverage'
}

defineProps<{
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

defineEmits<{
  close: []
  start: []
  'open-doc': [docId: number]
  'open-queue': []
  'open-logs': []
  'update:batchIndex': [value: number]
}>()
</script>
