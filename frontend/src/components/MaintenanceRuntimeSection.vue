<template>
  <section
    class="mt-6 rounded-xl border border-amber-200 bg-white p-6 shadow-sm dark:border-amber-900/50 dark:bg-slate-900"
  >
    <div class="flex flex-wrap items-center justify-between gap-4">
      <div>
        <h3 class="text-lg font-semibold text-amber-700 dark:text-amber-300">Worker lock</h3>
        <p class="text-sm text-slate-500 dark:text-slate-400">
          Inspect Redis worker lock ownership and TTL. Reset only if a stale lock blocks startup.
        </p>
      </div>
      <button
        class="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
        :disabled="workerLockLoading"
        @click="$emit('refresh-lock')"
      >
        <span v-if="workerLockLoading" class="inline-flex items-center gap-2">
          <Loader2 class="h-4 w-4 animate-spin" />
          Refreshing...
        </span>
        <span v-else>Refresh lock status</span>
      </button>
    </div>
    <div
      class="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-800 dark:text-slate-200"
    >
      <div class="grid gap-2 md:grid-cols-3">
        <div>
          <div class="text-xs uppercase tracking-wide text-slate-400 dark:text-slate-500">State</div>
          <div class="font-semibold">
            {{ workerLockStatus?.has_lock ? 'Lock set' : 'No lock' }}
          </div>
        </div>
          <div>
            <div class="text-xs uppercase tracking-wide text-slate-400 dark:text-slate-500">Owner</div>
            <div class="font-mono text-xs break-all">
              {{ workerLockStatus?.owner || '-' }}
            </div>
          </div>
        <div>
          <div class="text-xs uppercase tracking-wide text-slate-400 dark:text-slate-500">TTL</div>
          <div class="font-semibold">
            {{ workerLockStatusTtlLabel }}
          </div>
        </div>
      </div>
    </div>
    <div
      class="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800 dark:border-amber-900/50 dark:bg-amber-950/40 dark:text-amber-200"
    >
      Resetting the lock may cause a currently running worker to stop on its next lock refresh.
    </div>
    <div class="mt-4 flex items-center gap-3">
      <button
        class="rounded-lg border border-amber-200 bg-amber-50 px-4 py-2 text-sm font-semibold text-amber-700 hover:border-amber-300 dark:border-amber-900/50 dark:bg-amber-950/40 dark:text-amber-200"
        :disabled="workerLockResetLoading || !workerLockStatus?.has_lock"
        @click="$emit('reset-lock')"
      >
        <span v-if="workerLockResetLoading" class="inline-flex items-center gap-2">
          <Loader2 class="h-4 w-4 animate-spin" />
          Resetting...
        </span>
        <span v-else>Reset worker lock</span>
      </button>
      <div v-if="workerLockResetResult" class="text-xs text-slate-500 dark:text-slate-400">
        {{ workerLockResetResult.had_lock ? 'Lock existed' : 'No lock existed' }},
        {{ workerLockResetResult.reset ? 'reset done' : 'nothing reset' }}.
        <span v-if="workerLockResetResult.reason">Reason: {{ workerLockResetResult.reason }}.</span>
      </div>
    </div>
  </section>

</template>

<script setup lang="ts">
import { Loader2 } from 'lucide-vue-next'
import type { QueueWorkerLockReset, QueueWorkerLockStatus } from '../services/queue'

defineProps<{
  workerLockStatus: QueueWorkerLockStatus | null
  workerLockLoading: boolean
  workerLockResetLoading: boolean
  workerLockStatusTtlLabel: string
  workerLockResetResult: QueueWorkerLockReset | null
}>()

defineEmits<{
  (e: 'refresh-lock'): void
  (e: 'reset-lock'): void
}>()
</script>
