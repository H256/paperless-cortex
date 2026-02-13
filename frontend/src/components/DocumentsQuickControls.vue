<template>
  <div
    class="sticky top-16 z-20 mt-4 flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 bg-white/95 p-2 shadow-sm backdrop-blur dark:border-slate-800 dark:bg-slate-900/95"
  >
    <span class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
      Triage
    </span>
    <button
      v-for="item in reviewItems"
      :key="item.value"
      class="rounded-md border px-2.5 py-1 text-xs font-semibold"
      :class="buttonClass(selectedReviewStatus === item.value)"
      @click="$emit('update:selectedReviewStatus', item.value)"
    >
      {{ item.label }}
    </button>
    <button
      class="ml-auto rounded-md border border-slate-200 bg-white px-2.5 py-1 text-xs font-semibold text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
      @click="$emit('reset-quick-filters')"
    >
      Reset quick filters
    </button>
    <button
      class="rounded-md border border-slate-200 bg-white px-2.5 py-1 text-xs font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-slate-500"
      @click="$emit('open-writeback')"
    >
      Writeback queue
    </button>
    <button
      class="rounded-md border border-slate-200 bg-white px-2.5 py-1 text-xs font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-slate-500"
      @click="$emit('open-processing')"
    >
      Continue processing
    </button>

    <span class="ml-2 text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
      View
    </span>
    <button
      class="rounded-md border px-2.5 py-1 text-xs font-semibold"
      :class="buttonClass(viewMode === 'table')"
      @click="$emit('update:viewMode', 'table')"
    >
      Table
    </button>
    <button
      class="rounded-md border px-2.5 py-1 text-xs font-semibold"
      :class="buttonClass(viewMode === 'cards')"
      @click="$emit('update:viewMode', 'cards')"
    >
      Cards
    </button>
  </div>
</template>

<script setup lang="ts">
type ReviewStatus = 'all' | 'unreviewed' | 'reviewed' | 'needs_review'
type ViewMode = 'table' | 'cards'

defineProps<{
  selectedReviewStatus: ReviewStatus
  viewMode: ViewMode
}>()

defineEmits<{
  'update:selectedReviewStatus': [value: ReviewStatus]
  'update:viewMode': [value: ViewMode]
  'reset-quick-filters': []
  'open-writeback': []
  'open-processing': []
}>()

const reviewItems: Array<{ value: ReviewStatus; label: string }> = [
  { value: 'unreviewed', label: 'Unreviewed' },
  { value: 'needs_review', label: 'Needs review' },
  { value: 'reviewed', label: 'Reviewed' },
  { value: 'all', label: 'All' },
]

const buttonClass = (active: boolean) =>
  active
    ? 'border-indigo-300 bg-indigo-50 text-indigo-700 dark:border-indigo-900/50 dark:bg-indigo-950/30 dark:text-indigo-200'
    : 'border-slate-200 bg-white text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300'
</script>
