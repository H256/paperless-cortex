<template>
  <section
    class="mt-4 rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm dark:border-slate-800 dark:bg-slate-900"
  >
    <div class="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
      Presets
    </div>
    <div class="mt-2 flex flex-wrap gap-2">
      <button
        v-for="preset in presets"
        :key="preset.key"
        class="rounded-md border px-2.5 py-1 text-xs font-semibold"
        :class="buttonClass(preset.active)"
        @click="$emit('applyPreset', preset.key)"
      >
        {{ preset.label }}
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'

type AnalysisFilter = 'all' | 'analyzed' | 'not_analyzed'
type ReviewStatus = 'all' | 'unreviewed' | 'reviewed' | 'needs_review'
type PresetKey = 'unreviewed' | 'needs_review' | 'not_analyzed' | 'inbox'

const props = defineProps<{
  analysisFilter: AnalysisFilter
  reviewStatus: ReviewStatus
  searchQuery?: string
}>()

const hasSearchFilter = computed(() => Boolean(props.searchQuery?.trim()))

defineEmits<{
  applyPreset: [key: PresetKey]
}>()

const presets = computed(() => [
  {
    key: 'unreviewed' as const,
    label: 'Unreviewed',
    active: !hasSearchFilter.value && props.reviewStatus === 'unreviewed' && props.analysisFilter === 'all',
  },
  {
    key: 'needs_review' as const,
    label: 'Needs review',
    active: !hasSearchFilter.value && props.reviewStatus === 'needs_review' && props.analysisFilter === 'all',
  },
  {
    key: 'not_analyzed' as const,
    label: 'Not analyzed',
    active: !hasSearchFilter.value && props.analysisFilter === 'not_analyzed' && props.reviewStatus === 'all',
  },
  {
    key: 'inbox' as const,
    label: 'Inbox (new)',
    active:
      !hasSearchFilter.value &&
      props.reviewStatus === 'unreviewed' &&
      props.analysisFilter === 'not_analyzed',
  },
])

const buttonClass = (active: boolean) =>
  active
    ? 'border-indigo-300 bg-indigo-50 text-indigo-700 dark:border-indigo-900/50 dark:bg-indigo-950/30 dark:text-indigo-200'
    : 'border-slate-200 bg-white text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300'
</script>
