<template>
  <section
    class="mt-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900"
  >
    <div class="flex items-center justify-between gap-3">
      <div class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
        Filters
      </div>
      <button
        class="inline-flex items-center gap-1 rounded-md border border-slate-200 px-2 py-1 text-xs font-semibold text-slate-600 hover:border-slate-300 hover:text-slate-800 dark:border-slate-700 dark:text-slate-300 dark:hover:border-slate-500 dark:hover:text-slate-100"
        @click="advancedOpen = !advancedOpen"
      >
        Advanced
        <ChevronUp v-if="advancedOpen" class="h-3.5 w-3.5" />
        <ChevronDown v-else class="h-3.5 w-3.5" />
      </button>
    </div>
    <div class="mt-3 grid gap-4 md:grid-cols-3 lg:grid-cols-6">
      <div>
        <label class="flex items-center gap-2 text-xs font-semibold text-slate-500 dark:text-slate-400">
          Quick search
          <span
            class="rounded border border-slate-200 px-1.5 py-0.5 text-[10px] font-bold text-slate-500 dark:border-slate-700 dark:text-slate-400"
          >
            /
          </span>
        </label>
        <div class="relative mt-1">
          <input
            ref="searchInputRef"
            v-model="searchQueryModel"
            type="text"
            placeholder="ID, title, content..."
            class="w-full rounded-lg border border-slate-200 bg-white px-2 py-2 pr-8 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          />
          <button
            v-if="searchQueryModel.trim()"
            type="button"
            class="absolute right-1 top-1/2 -translate-y-1/2 rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-200"
            @click="searchQueryModel = ''"
            title="Clear search"
          >
            <X class="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
      <div>
        <label class="text-xs font-semibold text-slate-500 dark:text-slate-400">Sort</label>
        <select
          v-model="orderingModel"
          class="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-2 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
        >
          <option value="-date">Issue date desc</option>
          <option value="date">Issue date asc</option>
          <option value="-title">Title desc</option>
          <option value="title">Title asc</option>
        </select>
      </div>
      <div>
        <label class="text-xs font-semibold text-slate-500 dark:text-slate-400">Correspondent</label>
        <select
          v-model="selectedCorrespondentModel"
          class="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-2 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
        >
          <option value="">All</option>
          <option value="-1">Without correspondent</option>
          <option
            v-for="c in correspondents"
            :key="c.id ?? `corr-${c.name}`"
            :value="c.id != null ? String(c.id) : ''"
          >
            {{ c.name }}
          </option>
        </select>
      </div>
      <div>
        <label class="text-xs font-semibold text-slate-500 dark:text-slate-400">Tag</label>
        <select
          v-model="selectedTagModel"
          class="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-2 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
        >
          <option value="">All</option>
          <option v-for="t in tags" :key="t.id ?? `tag-${t.name}`" :value="t.id != null ? String(t.id) : ''">
            {{ t.name }}
          </option>
        </select>
      </div>
      <div>
        <label class="text-xs font-semibold text-slate-500 dark:text-slate-400">Analysis</label>
        <select
          v-model="analysisFilterModel"
          class="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-2 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
        >
          <option value="all">All</option>
          <option value="analyzed">Analyzed</option>
          <option value="not_analyzed">Not analyzed</option>
        </select>
      </div>
      <div>
        <label class="text-xs font-semibold text-slate-500 dark:text-slate-400">Review</label>
        <select
          v-model="selectedReviewStatusModel"
          class="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-2 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
        >
          <option value="all">All</option>
          <option value="unreviewed">Unreviewed</option>
          <option value="needs_review">Needs review</option>
          <option value="reviewed">Reviewed</option>
        </select>
      </div>
    </div>
    <div
      v-if="advancedOpen"
      class="mt-3 grid gap-4 rounded-lg border border-slate-200 bg-slate-50 p-3 md:grid-cols-2 lg:grid-cols-4 dark:border-slate-700 dark:bg-slate-800/40"
    >
      <div>
        <label class="text-xs font-semibold text-slate-500 dark:text-slate-400">From</label>
        <input
          type="date"
          v-model="dateFromModel"
          class="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-2 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
        />
      </div>
      <div>
        <label class="text-xs font-semibold text-slate-500 dark:text-slate-400">To</label>
        <input
          type="date"
          v-model="dateToModel"
          class="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-2 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
        />
      </div>
      <div>
        <label class="text-xs font-semibold text-slate-500 dark:text-slate-400">Model</label>
        <input
          v-model="modelFilterModel"
          type="text"
          placeholder="e.g. gpt-oss"
          class="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-2 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
        />
      </div>
      <div>
        <label class="text-xs font-semibold text-slate-500 dark:text-slate-400">Page size</label>
        <select
          v-model.number="pageSizeModel"
          class="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-2 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
        >
          <option :value="10">10</option>
          <option :value="20">20</option>
          <option :value="50">50</option>
        </select>
      </div>
    </div>

    <div class="mt-4 flex flex-wrap items-center gap-3 text-sm text-slate-600 dark:text-slate-300">
      <button
        class="ml-auto inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:border-slate-300 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
        @click="$emit('reload')"
        :disabled="props.isLoading"
        title="Reload current list"
      >
        <RefreshCw class="h-4 w-4" :class="{ 'animate-spin': props.isLoading }" />
        {{ props.isLoading ? 'Reloading...' : 'Reload' }}
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ChevronDown, ChevronUp, RefreshCw, X } from 'lucide-vue-next'
import type { Correspondent, Tag } from '../services/documents'

const props = defineProps<{
  tags: Tag[]
  correspondents: Correspondent[]
  ordering: string
  selectedCorrespondent: string
  selectedTag: string
  dateFrom: string
  dateTo: string
  analysisFilter: 'all' | 'analyzed' | 'not_analyzed'
  selectedReviewStatus: 'all' | 'unreviewed' | 'reviewed' | 'needs_review'
  modelFilter: string
  searchQuery: string
  pageSize: number
  isLoading?: boolean
}>()

const emit = defineEmits<{
  reload: []
  'update:ordering': [value: string]
  'update:selectedCorrespondent': [value: string]
  'update:selectedTag': [value: string]
  'update:dateFrom': [value: string]
  'update:dateTo': [value: string]
  'update:analysisFilter': [value: 'all' | 'analyzed' | 'not_analyzed']
  'update:selectedReviewStatus': [value: 'all' | 'unreviewed' | 'reviewed' | 'needs_review']
  'update:modelFilter': [value: string]
  'update:searchQuery': [value: string]
  'update:pageSize': [value: number]
}>()

const advancedOpen = ref(false)
const searchInputRef = ref<HTMLInputElement | null>(null)

const orderingModel = computed({
  get: () => props.ordering,
  set: (value: string) => emit('update:ordering', value),
})
const selectedCorrespondentModel = computed({
  get: () => props.selectedCorrespondent,
  set: (value: string) => emit('update:selectedCorrespondent', value),
})
const selectedTagModel = computed({
  get: () => props.selectedTag,
  set: (value: string) => emit('update:selectedTag', value),
})
const dateFromModel = computed({
  get: () => props.dateFrom,
  set: (value: string) => emit('update:dateFrom', value),
})
const dateToModel = computed({
  get: () => props.dateTo,
  set: (value: string) => emit('update:dateTo', value),
})
const analysisFilterModel = computed({
  get: () => props.analysisFilter,
  set: (value: 'all' | 'analyzed' | 'not_analyzed') => emit('update:analysisFilter', value),
})
const selectedReviewStatusModel = computed({
  get: () => props.selectedReviewStatus,
  set: (value: 'all' | 'unreviewed' | 'reviewed' | 'needs_review') =>
    emit('update:selectedReviewStatus', value),
})
const modelFilterModel = computed({
  get: () => props.modelFilter,
  set: (value: string) => emit('update:modelFilter', value),
})
const searchQueryModel = computed({
  get: () => props.searchQuery,
  set: (value: string) => emit('update:searchQuery', value),
})
const pageSizeModel = computed({
  get: () => props.pageSize,
  set: (value: number) => emit('update:pageSize', value),
})

watch(
  () => [props.dateFrom, props.dateTo, props.modelFilter, props.pageSize] as const,
  ([dateFrom, dateTo, modelFilter, pageSize]) => {
    if (dateFrom || dateTo || modelFilter.trim() || pageSize !== 20) {
      advancedOpen.value = true
    }
  },
  { immediate: true },
)

const isEditableTarget = (target: EventTarget | null): boolean => {
  if (!(target instanceof HTMLElement)) return false
  const tag = target.tagName.toLowerCase()
  return tag === 'input' || tag === 'textarea' || target.isContentEditable
}

const handleGlobalKeydown = (event: KeyboardEvent) => {
  if (event.key === '/' && !isEditableTarget(event.target)) {
    event.preventDefault()
    searchInputRef.value?.focus()
    searchInputRef.value?.select()
  }
  if (event.key === 'Escape' && document.activeElement === searchInputRef.value) {
    if (searchQueryModel.value) {
      searchQueryModel.value = ''
    }
    searchInputRef.value?.blur()
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleGlobalKeydown)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleGlobalKeydown)
})
</script>
