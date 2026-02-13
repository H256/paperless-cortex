<template>
  <section
    v-if="activeFilters.length > 0"
    class="mt-4 rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm dark:border-slate-800 dark:bg-slate-900"
  >
    <div class="flex flex-wrap items-center gap-2">
      <span class="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
        Active filters
      </span>
      <button
        class="ml-auto inline-flex items-center rounded-md border border-slate-200 px-2 py-1 text-xs font-semibold text-slate-600 hover:border-slate-300 hover:text-slate-800 dark:border-slate-700 dark:text-slate-300 dark:hover:border-slate-500 dark:hover:text-slate-100"
        @click="$emit('clearAll')"
      >
        Clear all
      </button>
    </div>
    <div class="mt-2 flex flex-wrap gap-2">
      <button
        v-for="item in activeFilters"
        :key="item.key"
        class="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-700 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:border-slate-500"
        @click="$emit('clearFilter', item.key)"
        :title="`Remove ${item.label} filter`"
      >
        <span class="font-semibold">{{ item.label }}:</span>
        <span class="truncate max-w-48">{{ item.value }}</span>
        <X class="h-3.5 w-3.5" />
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { X } from 'lucide-vue-next'
import type { Correspondent, Tag } from '../services/documents'

type AnalysisFilter = 'all' | 'analyzed' | 'not_analyzed'
type ReviewStatus = 'all' | 'unreviewed' | 'reviewed' | 'needs_review'
type FilterKey = 'correspondent' | 'tag' | 'date_from' | 'date_to' | 'analysis' | 'review' | 'model'

const props = defineProps<{
  tags: Tag[]
  correspondents: Correspondent[]
  selectedCorrespondent: string
  selectedTag: string
  dateFrom: string
  dateTo: string
  analysisFilter: AnalysisFilter
  selectedReviewStatus: ReviewStatus
  modelFilter: string
}>()

defineEmits<{
  clearAll: []
  clearFilter: [key: FilterKey]
}>()

const findNameById = <T extends { id?: number | null; name?: string | null }>(
  items: T[],
  idValue: string,
): string => {
  const id = Number(idValue)
  if (!Number.isFinite(id)) return idValue
  return items.find((item) => item.id === id)?.name?.trim() || idValue
}

const analysisLabel = (value: AnalysisFilter): string => {
  if (value === 'analyzed') return 'Analyzed'
  if (value === 'not_analyzed') return 'Not analyzed'
  return 'All'
}

const reviewLabel = (value: ReviewStatus): string => {
  if (value === 'unreviewed') return 'Unreviewed'
  if (value === 'reviewed') return 'Reviewed'
  if (value === 'needs_review') return 'Needs review'
  return 'All'
}

const activeFilters = computed(() => {
  const items: Array<{ key: FilterKey; label: string; value: string }> = []
  if (props.selectedCorrespondent) {
    items.push({
      key: 'correspondent',
      label: 'Correspondent',
      value: findNameById(props.correspondents, props.selectedCorrespondent),
    })
  }
  if (props.selectedTag) {
    items.push({
      key: 'tag',
      label: 'Tag',
      value: findNameById(props.tags, props.selectedTag),
    })
  }
  if (props.dateFrom) items.push({ key: 'date_from', label: 'From', value: props.dateFrom })
  if (props.dateTo) items.push({ key: 'date_to', label: 'To', value: props.dateTo })
  if (props.analysisFilter !== 'all') {
    items.push({ key: 'analysis', label: 'Analysis', value: analysisLabel(props.analysisFilter) })
  }
  if (props.selectedReviewStatus !== 'all') {
    items.push({
      key: 'review',
      label: 'Review',
      value: reviewLabel(props.selectedReviewStatus),
    })
  }
  if (props.modelFilter.trim()) {
    items.push({ key: 'model', label: 'Model', value: props.modelFilter.trim() })
  }
  return items
})
</script>
