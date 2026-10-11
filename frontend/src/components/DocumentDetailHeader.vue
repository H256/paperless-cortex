<template>
  <div class="flex flex-wrap items-start justify-between gap-4">
    <div>
      <h2 class="text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">
        {{ title || `Document ${docId}` }}
      </h2>
      <p class="text-sm text-slate-500 dark:text-slate-400">{{ headerMetaLine }}</p>
      <p
        v-if="activeRunLabel"
        class="mt-1 inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-indigo-50 px-2.5 py-1 text-xs font-semibold text-indigo-700 dark:border-indigo-900/50 dark:bg-indigo-950/30 dark:text-indigo-200"
      >
        Processing now: {{ activeRunLabel }}
      </p>
    </div>
    <div class="flex w-full flex-wrap items-center gap-2 md:w-auto md:justify-end">
      <div
        v-if="queuePosition"
        class="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-1.5 py-1 text-xs font-semibold text-slate-700 shadow-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
        data-testid="review-queue-nav"
      >
        <button
          type="button"
          class="rounded px-1.5 py-1 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-40 dark:hover:bg-slate-800"
          :disabled="!hasPrev"
          title="Previous document (k)"
          data-testid="review-prev"
          @click="$emit('prev')"
        >
          <ChevronLeft class="h-4 w-4" />
        </button>
        <span data-testid="review-position">{{ queuePosition.index + 1 }} / {{ queuePosition.total }}</span>
        <button
          type="button"
          class="rounded px-1.5 py-1 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-40 dark:hover:bg-slate-800"
          :disabled="!hasNext"
          title="Next document (j)"
          data-testid="review-next"
          @click="$emit('next')"
        >
          <ChevronRight class="h-4 w-4" />
        </button>
        <label
          class="ml-1 flex cursor-pointer items-center gap-1 border-l border-slate-200 pl-2 font-normal dark:border-slate-700"
          title="Jump to the next document after marking reviewed or writing back"
        >
          <input
            type="checkbox"
            :checked="autoAdvance"
            data-testid="review-auto-advance"
            @change="$emit('update:autoAdvance', ($event.target as HTMLInputElement).checked)"
          />
          Auto-advance
        </label>
      </div>
      <button
        class="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 shadow-sm hover:border-slate-300 sm:text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
        @click="$emit('back')"
      >
        <ArrowLeft class="h-4 w-4" />
        Back
      </button>
      <IconButton
        v-if="paperlessUrl"
        :href="paperlessUrl"
        title="Open document in Paperless"
        aria-label="Open document in Paperless"
      >
        <ExternalLink class="h-5 w-5" />
      </IconButton>
      <IconButton
        v-else
        disabled
        title="Set VITE_PAPERLESS_BASE_URL to enable link"
        aria-label="Paperless link unavailable"
      >
        <ExternalLink class="h-5 w-5" />
      </IconButton>
      <button
        class="inline-flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-700 shadow-sm hover:border-emerald-300 sm:text-sm dark:border-emerald-900/50 dark:bg-emerald-950/30 dark:text-emerald-200"
        :disabled="reviewMarking || !canMarkReviewed"
        :class="reviewMarking || !canMarkReviewed ? 'cursor-not-allowed opacity-70' : ''"
        title="Marks this document as reviewed without applying suggestions."
        @click="$emit('mark-reviewed')"
      >
        <CheckCircle class="h-4 w-4" :class="reviewMarking ? 'animate-pulse' : ''" />
        {{ reviewMarking ? 'Marking...' : 'Mark reviewed' }}
      </button>
      <button
        class="inline-flex items-center gap-2 rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-2 text-xs font-semibold text-indigo-700 shadow-sm hover:border-indigo-300 sm:text-sm dark:border-indigo-900/50 dark:bg-indigo-950/30 dark:text-indigo-200"
        :disabled="writebackRunning || !canWriteback"
        :class="writebackRunning || !canWriteback ? 'cursor-not-allowed opacity-70' : ''"
        :title="writebackButtonTitle"
        @click="$emit('open-writeback-confirm')"
      >
        <ClipboardCheck class="h-4 w-4" :class="writebackRunning ? 'animate-pulse' : ''" />
        {{ writebackButtonLabel }}
      </button>
      <button
        class="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-3 py-2 text-xs font-semibold text-white shadow-sm hover:bg-slate-800 sm:text-sm"
        :disabled="reloadingAll"
        :class="reloadingAll ? 'cursor-not-allowed opacity-70' : ''"
        @click="$emit('reload')"
      >
        <RefreshCw class="h-4 w-4" :class="reloadingAll ? 'animate-spin' : ''" />
        {{ reloadingAll ? 'Reloading...' : 'Reload' }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import {
  ArrowLeft,
  CheckCircle,
  ChevronLeft,
  ChevronRight,
  ClipboardCheck,
  ExternalLink,
  RefreshCw,
} from 'lucide-vue-next'
import IconButton from './IconButton.vue'

withDefaults(defineProps<{
  title: string
  docId: number
  headerMetaLine: string
  activeRunLabel: string
  paperlessUrl: string
  reviewMarking: boolean
  canMarkReviewed: boolean
  writebackRunning: boolean
  canWriteback: boolean
  writebackButtonTitle: string
  writebackButtonLabel: string
  reloadingAll: boolean
  queuePosition?: { index: number; total: number } | null
  hasPrev?: boolean
  hasNext?: boolean
  autoAdvance?: boolean
}>(), { queuePosition: null, hasPrev: false, hasNext: false, autoAdvance: true })

defineEmits<{
  back: []
  'mark-reviewed': []
  'open-writeback-confirm': []
  reload: []
  prev: []
  next: []
  'update:autoAdvance': [value: boolean]
}>()
</script>
