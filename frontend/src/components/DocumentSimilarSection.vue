<template>
  <section class="space-y-4">
    <div class="flex items-center justify-between">
      <div>
        <h3 class="text-lg font-semibold text-slate-900 dark:text-slate-100">Similar documents</h3>
        <p class="text-xs text-slate-500 dark:text-slate-400">Top matches from embeddings.</p>
      </div>
      <button
        class="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
        :disabled="loading"
        @click="$emit('refresh')"
      >
        Refresh
      </button>
    </div>

    <div class="grid gap-3 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs dark:border-slate-700 dark:bg-slate-900/60 md:grid-cols-2">
      <label class="block">
        <div class="mb-1 font-semibold text-slate-700 dark:text-slate-200">
          Similar min score (0.50-1.00): {{ similarMinScore.toFixed(2) }}
        </div>
        <div class="flex items-center gap-2">
          <input
            type="range"
            min="0.5"
            max="1"
            step="0.01"
            :value="similarMinScore"
            class="w-full"
            @input="onSimilarRangeInput"
          />
          <input
            type="number"
            min="0.5"
            max="1"
            step="0.01"
            :value="similarMinScore"
            class="w-20 rounded border border-slate-300 px-1 py-0.5 text-xs dark:border-slate-600 dark:bg-slate-800"
            @input="onSimilarNumberInput"
          />
        </div>
      </label>

      <label class="block">
        <div class="mb-1 font-semibold text-slate-700 dark:text-slate-200">
          Duplicate threshold (0.80-1.00): {{ duplicateThreshold.toFixed(2) }}
        </div>
        <div class="flex items-center gap-2">
          <input
            type="range"
            min="0.8"
            max="1"
            step="0.01"
            :value="duplicateThreshold"
            class="w-full"
            @input="onDuplicateRangeInput"
          />
          <input
            type="number"
            min="0.8"
            max="1"
            step="0.01"
            :value="duplicateThreshold"
            class="w-20 rounded border border-slate-300 px-1 py-0.5 text-xs dark:border-slate-600 dark:bg-slate-800"
            @input="onDuplicateNumberInput"
          />
        </div>
      </label>
    </div>

    <div
      v-if="error"
      class="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-200"
    >
      {{ error }}
    </div>
    <div v-else-if="loading" class="text-sm text-slate-500 dark:text-slate-400">Loading...</div>
    <div v-else-if="!similarMatches.length" class="text-sm text-slate-500 dark:text-slate-400">
      No similar documents found.
    </div>
    <div v-else class="space-y-3">
      <DocumentCard
        v-for="match in similarMatches"
        :key="`similar-${match.doc_id}`"
        :doc="match.document"
        :paperless-base-url="paperlessBaseUrl"
        :show-summary="true"
        :show-processing-badges="true"
        :show-actions="true"
        :show-copy-id="false"
        :show-open="true"
        :show-continue="false"
        :show-review="false"
        @open="onOpenDoc"
      />
    </div>

    <div class="pt-2 border-t border-slate-200 dark:border-slate-700"></div>

    <div class="flex items-center justify-between">
      <div>
        <h3 class="text-lg font-semibold text-slate-900 dark:text-slate-100">Possible duplicates</h3>
        <p class="text-xs text-slate-500 dark:text-slate-400">
          High similarity matches (thresholded).
        </p>
      </div>
    </div>

    <div v-if="!duplicateMatches.length" class="text-sm text-slate-500 dark:text-slate-400">
      No duplicates detected.
    </div>
    <div v-else class="space-y-3">
      <DocumentCard
        v-for="match in duplicateMatches"
        :key="`dup-${match.doc_id}`"
        :doc="match.document"
        :paperless-base-url="paperlessBaseUrl"
        :show-summary="true"
        :show-processing-badges="true"
        :show-actions="true"
        :show-copy-id="false"
        :show-open="true"
        :show-continue="false"
        :show-review="false"
        @open="onOpenDoc"
      />
    </div>
  </section>
</template>

<script setup lang="ts">
import DocumentCard from './DocumentCard.vue'
import type { DocumentRow } from '../services/documents'

type SimilarMatch = {
  doc_id: number
  score?: number | null
  document: DocumentRow
}

defineProps<{
  similarMatches: SimilarMatch[]
  duplicateMatches: SimilarMatch[]
  loading: boolean
  error: string
  similarMinScore: number
  duplicateThreshold: number
  paperlessBaseUrl?: string | null
}>()

const emit = defineEmits<{
  (e: 'refresh'): void
  (e: 'open-doc', id: number): void
  (e: 'update:similar-min-score', value: number): void
  (e: 'update:duplicate-threshold', value: number): void
}>()

const onOpenDoc = (id: number | null | undefined) => {
  if (typeof id !== 'number') return
  emit('open-doc', id)
}

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value))

const onSimilarRangeInput = (event: Event) => {
  const raw = Number((event.target as HTMLInputElement).value)
  if (!Number.isFinite(raw)) return
  emit('update:similar-min-score', clamp(raw, 0.5, 1))
}

const onSimilarNumberInput = (event: Event) => {
  const raw = Number((event.target as HTMLInputElement).value)
  if (!Number.isFinite(raw)) return
  emit('update:similar-min-score', clamp(raw, 0.5, 1))
}

const onDuplicateRangeInput = (event: Event) => {
  const raw = Number((event.target as HTMLInputElement).value)
  if (!Number.isFinite(raw)) return
  emit('update:duplicate-threshold', clamp(raw, 0.8, 1))
}

const onDuplicateNumberInput = (event: Event) => {
  const raw = Number((event.target as HTMLInputElement).value)
  if (!Number.isFinite(raw)) return
  emit('update:duplicate-threshold', clamp(raw, 0.8, 1))
}
</script>
