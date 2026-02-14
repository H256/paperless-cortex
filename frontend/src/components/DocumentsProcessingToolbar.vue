<template>
  <section
    class="mt-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900"
  >
    <div class="flex w-full flex-wrap items-center justify-start gap-2 lg:justify-end">
      <button
        class="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
        @click="$emit('open-queue')"
        title="Open queue monitor"
      >
        Queue
      </button>
      <button
        class="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
        @click="$emit('open-logs')"
        title="Open processing logs"
      >
        Logs
      </button>
      <button
        class="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
        :disabled="continueProcessingRunning || processingKickoffPending || isProcessing"
        @click="$emit('open-preview')"
        title="Sync new documents and process missing intelligence items"
      >
        <RefreshCw class="h-4 w-4" :class="{ 'animate-spin': continueProcessingRunning || processingKickoffPending }" />
        {{ processingKickoffPending ? 'Starting...' : continueProcessingRunning ? 'Working...' : 'Continue processing' }}
      </button>
      <button
        v-if="showCancel"
        class="inline-flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm font-semibold text-rose-700 shadow-sm hover:border-rose-300 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-200"
        @click="$emit('cancel-processing')"
        title="Cancel processing and clear queued jobs"
      >
        <XCircle class="h-4 w-4" />
        Cancel processing
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { RefreshCw, XCircle } from 'lucide-vue-next'

defineProps<{
  continueProcessingRunning: boolean
  processingKickoffPending: boolean
  isProcessing: boolean
  showCancel: boolean
}>()

defineEmits<{
  'open-preview': []
  'cancel-processing': []
  'open-queue': []
  'open-logs': []
}>()
</script>
