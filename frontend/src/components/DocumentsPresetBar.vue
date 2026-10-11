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
        :title="`Shortcut: ${preset.shortcut}`"
      >
        {{ preset.label }}
        <span
          v-if="preset.count != null"
          class="ml-1 rounded-full bg-slate-100 px-1.5 text-[10px] font-semibold text-slate-600 dark:bg-slate-800 dark:text-slate-300"
          :data-testid="`preset-count-${preset.key}`"
          >{{ preset.count }}</span
        >
        <span class="text-[10px] opacity-70">{{ preset.shortcut }}</span>
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from 'vue'

type AnalysisFilter = 'all' | 'analyzed' | 'not_analyzed'
type ReviewStatus = 'all' | 'unreviewed' | 'reviewed' | 'needs_review'
type PresetKey =
  | 'unreviewed'
  | 'needs_review'
  | 'not_analyzed'
  | 'inbox'
  | 'no_correspondent'
  | 'import_date'

const props = defineProps<{
  analysisFilter: AnalysisFilter
  reviewStatus: ReviewStatus
  searchQuery?: string
  selectedCorrespondent?: string
  issueDateIsImportDate?: boolean
  /** Library-wide counters from the review summary; missing keys show no counter. */
  counts?: Partial<Record<PresetKey, number>>
}>()

const hasSearchFilter = computed(() => Boolean(props.searchQuery?.trim()))

const presets = computed(() => [
  {
    key: 'unreviewed' as const,
    label: 'Unreviewed',
    count: props.counts?.unreviewed,
    shortcut: 'Alt+1',
    active: !hasSearchFilter.value && props.reviewStatus === 'unreviewed' && props.analysisFilter === 'all',
  },
  {
    key: 'needs_review' as const,
    label: 'Needs review',
    count: props.counts?.needs_review,
    shortcut: 'Alt+2',
    active: !hasSearchFilter.value && props.reviewStatus === 'needs_review' && props.analysisFilter === 'all',
  },
  {
    key: 'not_analyzed' as const,
    label: 'Not analyzed',
    count: props.counts?.not_analyzed,
    shortcut: 'Alt+3',
    active: !hasSearchFilter.value && props.analysisFilter === 'not_analyzed' && props.reviewStatus === 'all',
  },
  {
    key: 'inbox' as const,
    label: 'Inbox (new)',
    count: props.counts?.inbox,
    shortcut: 'Alt+4',
    active:
      !hasSearchFilter.value &&
      props.reviewStatus === 'unreviewed' &&
      props.analysisFilter === 'not_analyzed',
  },
  {
    // Filter presets: they keep the other filters (e.g. "Unreviewed") and toggle on/off.
    key: 'no_correspondent' as const,
    label: 'No correspondent',
    count: props.counts?.no_correspondent,
    shortcut: 'Alt+5',
    active: props.selectedCorrespondent === '-1',
  },
  {
    key: 'import_date' as const,
    label: 'Issue date = import date',
    count: props.counts?.import_date,
    shortcut: 'Alt+6',
    active: Boolean(props.issueDateIsImportDate),
  },
])

const buttonClass = (active: boolean) =>
  active
    ? 'border-indigo-300 bg-indigo-50 text-indigo-700 dark:border-indigo-900/50 dark:bg-indigo-950/30 dark:text-indigo-200'
    : 'border-slate-200 bg-white text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300'

const emit = defineEmits<{
  applyPreset: [key: PresetKey]
}>()

const isEditableTarget = (target: EventTarget | null): boolean => {
  if (!(target instanceof HTMLElement)) return false
  const tag = target.tagName.toLowerCase()
  return tag === 'input' || tag === 'textarea' || target.isContentEditable
}

const handleKeydown = (event: KeyboardEvent) => {
  if (!event.altKey || isEditableTarget(event.target)) return
  if (event.key === '1') emit('applyPreset', 'unreviewed')
  if (event.key === '2') emit('applyPreset', 'needs_review')
  if (event.key === '3') emit('applyPreset', 'not_analyzed')
  if (event.key === '4') emit('applyPreset', 'inbox')
  if (event.key === '5') emit('applyPreset', 'no_correspondent')
  if (event.key === '6') emit('applyPreset', 'import_date')
}

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleKeydown)
})
</script>
