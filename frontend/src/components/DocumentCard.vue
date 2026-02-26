<template>
  <button
    class="block w-full rounded-lg border border-slate-200 bg-slate-50 p-3 text-left hover:border-slate-300 dark:border-slate-700 dark:bg-slate-800 dark:hover:border-slate-600"
    @click="emit('open', doc.id)"
  >
    <div class="text-sm font-semibold text-slate-900 dark:text-slate-100">
      {{ doc.title || `Document ${doc.id ?? '-'}` }}
    </div>
    <div class="mt-1 text-xs text-slate-500 dark:text-slate-400">
      {{ formatDate(doc.document_date || doc.created) || '-' }}
      <span v-if="correspondentLabel"> | {{ correspondentLabel }}</span>
    </div>
    <div
      v-if="showSummary && summaryPreview"
      class="mt-2 line-clamp-3 text-xs text-slate-600 dark:text-slate-300"
      :title="summaryPreview"
    >
      {{ summaryPreview }}
    </div>
    <div class="mt-2 flex flex-wrap items-center gap-2">
      <div
        class="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-2 py-1 text-xs dark:border-slate-700 dark:bg-slate-900"
        :title="doc.local_cached ? 'Paperless + local cache' : 'Paperless only'"
      >
        <Database class="h-3.5 w-3.5" :class="doc.local_cached ? 'text-indigo-600' : 'text-slate-400'" />
        <span class="text-slate-500 dark:text-slate-400">{{ doc.local_cached ? 'Cached' : 'Paperless' }}</span>
      </div>
      <a
        v-if="paperlessBaseUrl"
        class="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
        :href="paperlessDocUrl(doc.id ?? 0)"
        target="_blank"
        rel="noopener"
        @click.stop
      >
        <ExternalLink class="h-3 w-3" />
        Paperless
      </a>
      <div
        v-if="doc.local_overrides"
        class="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2 py-1 text-xs dark:border-amber-900/50 dark:bg-amber-950/40"
        title="Local values override Paperless"
      >
        <Pencil class="h-3.5 w-3.5 text-amber-600" />
        <span class="text-amber-700 dark:text-amber-300">Overrides</span>
      </div>
    </div>
    <div v-if="showProcessingBadges" class="mt-2 space-y-1">
      <DocumentProcessingBadges :doc="doc" />
      <div
        v-if="doc.id != null && runningLabel"
        class="inline-flex items-center rounded-full border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-[11px] font-semibold text-indigo-700 dark:border-indigo-900/50 dark:bg-indigo-950/30 dark:text-indigo-200"
        :title="runningLabel"
      >
        {{ runningLabel }}
      </div>
    </div>
    <div v-if="showActions" class="mt-3 flex flex-wrap items-center gap-2">
      <button
        v-if="showCopyId"
        type="button"
        class="rounded-md border border-slate-200 bg-white px-2.5 py-1 text-xs font-semibold text-slate-700 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
        @click.stop="emit('copy-id', doc.id)"
      >
        {{ copied ? 'Copied' : 'Copy ID' }}
      </button>
      <button
        v-if="showOpen"
        type="button"
        class="rounded-md border border-slate-200 bg-white px-2.5 py-1 text-xs font-semibold text-slate-700 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
        @click.stop="emit('open', doc.id)"
      >
        Open
      </button>
      <button
        v-if="showContinue"
        type="button"
        class="rounded-md border border-indigo-200 bg-indigo-50 px-2.5 py-1 text-xs font-semibold text-indigo-700 hover:border-indigo-300 dark:border-indigo-900/50 dark:bg-indigo-950/30 dark:text-indigo-200"
        @click.stop="emit('open-operations', doc.id)"
      >
        Continue
      </button>
      <button
        v-if="showReview && needsReview"
        type="button"
        class="rounded-md border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-700 hover:border-amber-300 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-200"
        @click.stop="emit('open-suggestions', doc.id)"
      >
        Review
      </button>
    </div>
  </button>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Database, ExternalLink, Pencil } from 'lucide-vue-next'
import DocumentProcessingBadges from './DocumentProcessingBadges.vue'
import type { DocumentRow } from '../services/documents'

const props = defineProps<{
  doc: DocumentRow
  paperlessBaseUrl?: string | null
  runningLabel?: string | null
  copied?: boolean
  showSummary?: boolean
  showProcessingBadges?: boolean
  showActions?: boolean
  showCopyId?: boolean
  showOpen?: boolean
  showContinue?: boolean
  showReview?: boolean
}>()

const emit = defineEmits<{
  (e: 'open', id: number | null | undefined): void
  (e: 'open-operations', id: number | null | undefined): void
  (e: 'open-suggestions', id: number | null | undefined): void
  (e: 'copy-id', id: number | null | undefined): void
}>()

const summaryPreview = computed(() => {
  const value = (props.doc as unknown as Record<string, unknown>).ai_summary_preview
  return typeof value === 'string' ? value : ''
})

const needsReview = computed(
  () => props.doc.review_status === 'needs_review' || Boolean(props.doc.local_overrides),
)

const correspondentLabel = computed(() => {
  if (props.doc.correspondent_name) return props.doc.correspondent_name
  if (!props.doc.correspondent) return ''
  return String(props.doc.correspondent)
})

const paperlessDocUrl = (id: number) =>
  props.paperlessBaseUrl ? `${props.paperlessBaseUrl.replace(/\/$/, '')}/documents/${id}` : ''

const formatDate = (value?: string | null) => {
  if (!value) return ''
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return new Intl.DateTimeFormat(navigator.language).format(parsed)
}
</script>
