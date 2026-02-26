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

const props = defineProps<{
  similarMatches: SimilarMatch[]
  duplicateMatches: SimilarMatch[]
  loading: boolean
  error: string
  paperlessBaseUrl?: string | null
}>()

const emit = defineEmits<{
  (e: 'refresh'): void
  (e: 'open-doc', id: number): void
}>()

const onOpenDoc = (id: number | null | undefined) => {
  if (typeof id !== 'number') return
  emit('open-doc', id)
}
</script>
