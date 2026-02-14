<template>
  <section
    class="mt-6 rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center shadow-sm dark:border-slate-700 dark:bg-slate-900"
  >
    <h3 class="text-base font-semibold text-slate-900 dark:text-slate-100">
      {{ titleText }}
    </h3>
    <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">
      {{ descriptionText }}
    </p>
    <div class="mt-4 flex flex-wrap items-center justify-center gap-2">
      <button
        class="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
        @click="$emit('clearFilters')"
      >
        Clear filters
      </button>
      <button
        class="rounded-md border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-xs font-semibold text-indigo-700 hover:border-indigo-300 dark:border-indigo-900/50 dark:bg-indigo-950/30 dark:text-indigo-200"
        @click="$emit('openProcessing')"
      >
        Continue processing
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  mode?: 'filtered' | 'running_only' | 'empty'
}>()

defineEmits<{
  clearFilters: []
  openProcessing: []
}>()

const titleText = computed(() => {
  if (props.mode === 'running_only') return 'No running documents right now'
  if (props.mode === 'empty') return 'No documents available yet'
  return 'No documents match current filters'
})

const descriptionText = computed(() => {
  if (props.mode === 'running_only') {
    return 'Background work is currently idle. Disable running-only filter or enqueue processing.'
  }
  if (props.mode === 'empty') {
    return 'Sync documents from Paperless or continue processing to build local intelligence data.'
  }
  return 'Adjust filters or continue processing to generate more results.'
})
</script>
