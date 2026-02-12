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
</script>
