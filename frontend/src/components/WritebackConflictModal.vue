<template>
  <div
    v-if="open"
    class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 px-4"
  >
    <div
      class="w-full max-w-3xl rounded-xl border border-slate-200 bg-white p-5 shadow-xl dark:border-slate-700 dark:bg-slate-900"
    >
      <div class="text-base font-semibold text-slate-900 dark:text-slate-100">
        Resolve writeback conflicts
      </div>
      <p class="mt-2 text-sm text-slate-600 dark:text-slate-300">
        Paperless changed since this document was loaded. Choose how each field should be handled.
      </p>
      <div class="mt-4 space-y-3">
        <div
          v-for="conflict in conflicts"
          :key="conflict.field"
          class="rounded-lg border border-slate-200 p-3 dark:border-slate-700"
        >
          <div class="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            {{ conflictFieldLabel(conflict.field) }}
          </div>
          <div class="mt-2 grid gap-3 md:grid-cols-2">
            <div>
              <div class="text-[11px] font-semibold text-slate-500 dark:text-slate-400">Paperless</div>
              <div class="mt-1 whitespace-pre-wrap rounded-md bg-slate-50 p-2 text-xs text-slate-700 dark:bg-slate-800 dark:text-slate-200">
                {{ conflictValue(conflict.paperless) }}
              </div>
            </div>
            <div>
              <div class="text-[11px] font-semibold text-slate-500 dark:text-slate-400">Local</div>
              <div class="mt-1 whitespace-pre-wrap rounded-md bg-slate-50 p-2 text-xs text-slate-700 dark:bg-slate-800 dark:text-slate-200">
                {{ conflictValue(conflict.local) }}
              </div>
            </div>
          </div>
          <div class="mt-3">
            <select
              :value="resolutions[conflict.field] || 'skip'"
              class="w-full rounded-lg border border-slate-200 bg-white px-2 py-2 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
              @change="$emit('set-resolution', conflict.field, ($event.target as HTMLSelectElement).value as ResolutionValue)"
            >
              <option value="skip">Skip</option>
              <option value="use_paperless">Use Paperless (sync local)</option>
              <option value="use_local">Use Local (writeback)</option>
            </select>
          </div>
        </div>
      </div>
      <div class="mt-4 flex justify-end gap-2">
        <button
          class="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-slate-500"
          @click="$emit('cancel')"
        >
          Cancel
        </button>
        <button
          class="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-sm font-semibold text-emerald-700 hover:border-emerald-300 dark:border-emerald-900/50 dark:bg-emerald-950/40 dark:text-emerald-200"
          :disabled="running"
          @click="$emit('apply')"
        >
          Apply decisions
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { WritebackConflictField } from '../services/writeback'
import { conflictFieldLabel, conflictValue } from '../utils/writebackConflict'

type ResolutionValue = 'skip' | 'use_paperless' | 'use_local'

defineProps<{
  open: boolean
  running: boolean
  conflicts: WritebackConflictField[]
  resolutions: Record<string, ResolutionValue>
}>()

defineEmits<{
  cancel: []
  apply: []
  'set-resolution': [field: string, value: ResolutionValue]
}>()
</script>
