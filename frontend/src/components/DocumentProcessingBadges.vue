<template>
  <div class="flex flex-nowrap items-center gap-1 text-xs text-slate-400 whitespace-nowrap">
    <template v-if="missingItems.length">
      <div
        v-for="item in missingItems"
        :key="item.label"
        class="inline-flex items-center gap-1"
        :title="`Missing ${item.label}`"
      >
        <component :is="item.icon" class="h-3 w-3 text-amber-500" />
        <span class="sr-only">Missing {{ item.label }}</span>
      </div>
      <div
        v-if="fulfilledCount > 0"
        class="inline-flex items-center gap-1 text-[10px] font-semibold text-slate-400"
        :title="fulfilledTooltip"
      >
        +{{ fulfilledCount }}
      </div>
    </template>
    <template v-else>
      <div class="inline-flex items-center gap-1" title="All processed">
        <CheckCircle class="h-3 w-3 text-emerald-500" />
        <span class="sr-only">All processed</span>
      </div>
    </template>
    <span
      v-if="writebackBadge"
      class="inline-flex items-center rounded-full border px-1.5 py-0.5 text-[10px] font-semibold"
      :class="writebackBadge.className"
      :title="writebackBadge.title"
    >
      {{ writebackBadge.label }}
    </span>
  </div>
</template>

<script setup lang="ts">
import { computed, type Component } from 'vue'
import { CheckCircle, Eye, Layers, Lightbulb, RefreshCw, ScanText } from 'lucide-vue-next'
import type { DocumentRow } from '../services/documents'

const props = defineProps<{
  doc: DocumentRow
}>()

const missingItems = computed(() => {
  const items: { label: string; icon: Component }[] = []
  const doc = props.doc
  if (!doc.has_embeddings) items.push({ label: 'Embeddings', icon: Layers })
  if (!doc.has_vision_pages) items.push({ label: 'Vision OCR', icon: ScanText })
  if (!doc.has_suggestions_paperless)
    items.push({ label: 'Suggestions (paperless)', icon: Lightbulb })
  if (doc.has_vision_pages && !doc.has_suggestions_vision)
    items.push({ label: 'Suggestions (vision)', icon: Eye })
  if (!doc.local_cached) items.push({ label: 'Local cache', icon: RefreshCw })
  const order = new Map<string, number>([
    ['Embeddings', 1],
    ['Vision OCR', 2],
    ['Suggestions (paperless)', 3],
    ['Suggestions (vision)', 4],
    ['Local cache', 5],
  ])
  return items.sort((a, b) => (order.get(a.label) ?? 99) - (order.get(b.label) ?? 99))
})

const fulfilledCount = computed(() => {
  const doc = props.doc
  let count = 0
  if (doc.has_embeddings) count += 1
  if (doc.has_vision_pages) count += 1
  if (doc.has_suggestions_paperless) count += 1
  if (doc.has_vision_pages && doc.has_suggestions_vision) count += 1
  if (doc.local_cached) count += 1
  return count
})

const fulfilledTooltip = computed(() => {
  const doc = props.doc
  const done: string[] = []
  if (doc.has_embeddings) done.push('Embeddings')
  if (doc.has_vision_pages) done.push('Vision OCR')
  if (doc.has_suggestions_paperless) done.push('Suggestions (paperless)')
  if (doc.has_vision_pages && doc.has_suggestions_vision) done.push('Suggestions (vision)')
  if (doc.local_cached) done.push('Local cache')
  if (!done.length) return 'Nothing processed yet'
  return `Done: ${done.join(', ')}`
})

const writebackBadge = computed(() => {
  const status = String(props.doc.review_status || '').trim().toLowerCase()
  const hasOverrides = Boolean(props.doc.local_overrides)
  if (status === 'needs_review') {
    return {
      label: 'Needs review',
      title: 'Local suggestions exist and await your decision before writeback.',
      className:
        'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/50 dark:bg-amber-950/40 dark:text-amber-200',
    }
  }
  if (status === 'reviewed') {
    return {
      label: 'Reviewed',
      title: 'Document was reviewed; writeback decision is settled.',
      className:
        'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/50 dark:bg-emerald-950/30 dark:text-emerald-200',
    }
  }
  if (hasOverrides) {
    return {
      label: 'Local overrides',
      title: 'Local metadata differs from Paperless values.',
      className:
        'border-indigo-200 bg-indigo-50 text-indigo-700 dark:border-indigo-900/50 dark:bg-indigo-950/30 dark:text-indigo-200',
    }
  }
  return null
})
</script>
