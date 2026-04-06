<template>
  <section>
    <div class="flex flex-wrap items-center justify-between gap-4">
      <div>
        <h2 class="text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">
          Operations
        </h2>
        <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Operational controls for resets, cleanup, and runtime inspection.
        </p>
      </div>
    </div>

    <section
      class="mt-6 rounded-xl border border-rose-200 bg-white p-6 shadow-sm dark:border-rose-900/50 dark:bg-slate-900"
    >
      <div class="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h3 class="text-lg font-semibold text-rose-700 dark:text-rose-300">
            Reprocess all documents
          </h3>
          <p class="text-sm text-slate-500 dark:text-slate-400">
            Clears all intelligence data and rebuilds everything from scratch.
          </p>
        </div>
        <button
          class="inline-flex items-center gap-2 rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-rose-500"
          :disabled="syncing || isProcessing"
          @click="openReprocessModal"
        >
          <RefreshCcw class="h-4 w-4" />
          Reprocess all
        </button>
      </div>
      <div
        class="mt-4 rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-200"
      >
        This action cannot be undone. Paperless data is not modified.
      </div>
    </section>

    <section
      class="mt-6 rounded-xl border border-rose-200 bg-white p-6 shadow-sm dark:border-rose-900/50 dark:bg-slate-900"
    >
      <div class="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h3 class="text-lg font-semibold text-rose-700 dark:text-rose-300">Wipe local data</h3>
          <p class="text-sm text-slate-500 dark:text-slate-400">
            Removes all documents and intelligence data without reprocessing.
          </p>
        </div>
        <button
          class="inline-flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-sm font-semibold text-rose-700 hover:border-rose-300 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-200"
          :disabled="clearAllLoading"
          @click="openClearAllModal"
        >
          <span v-if="clearAllLoading" class="inline-flex items-center gap-2">
            <Loader2 class="h-4 w-4 animate-spin" />
            Clearing...
          </span>
          <span v-else>Wipe data</span>
        </button>
      </div>
      <div
        class="mt-4 rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-200"
      >
        This action cannot be undone. Paperless data is not modified, so documents will still appear
        from Paperless until you stop syncing.
      </div>
      <div
        v-if="clearAllResult"
        class="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800 dark:border-amber-900/40 dark:bg-amber-950/40 dark:text-amber-200"
      >
        Removed {{ clearAllResult.cleared_documents }} documents,
        {{ clearAllResult.cleared_embeddings }} embeddings,
        {{ clearAllResult.cleared_suggestions }} suggestions,
        {{ clearAllResult.cleared_page_texts }} vision OCR rows. Qdrant deleted:
        {{ clearAllResult.qdrant_deleted }}, errors: {{ clearAllResult.qdrant_errors }}.
      </div>
    </section>

    <section class="mt-6 grid gap-4 lg:grid-cols-4">
      <MaintenanceActionCard
        title="Remove Vision OCR"
        description="Deletes all stored vision OCR pages. Documents will need OCR again."
        action-label="Remove vision OCR"
        loading-label="Removing..."
        :loading="visionLoading"
        :result-text="visionResultText"
        @action="confirmVision"
      />

      <MaintenanceActionCard
        title="Remove Suggestions"
        description="Deletes all AI suggestions across documents."
        action-label="Remove suggestions"
        loading-label="Removing..."
        :loading="suggestionsLoading"
        :result-text="suggestionsResultText"
        @action="confirmSuggestions"
      />

      <MaintenanceActionCard
        title="Remove Embeddings"
        description="Deletes all embeddings (paperless + vision) and clears Qdrant points."
        action-label="Remove embeddings"
        loading-label="Removing..."
        :loading="embeddingsLoading"
        :result-text="embeddingsResultText"
        @action="confirmEmbeddings"
      />

      <MaintenanceActionCard
        title="Reset Similarity Index"
        description="Deletes all doc-level similarity vectors and similarity task history so indices can be rebuilt cleanly."
        action-label="Reset similarity index"
        loading-label="Resetting..."
        :loading="similarityIndexLoading"
        :result-text="similarityIndexResultText"
        @action="confirmSimilarityIndex"
      />

      <div
        class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900"
      >
        <h3 class="text-lg font-semibold text-slate-900 dark:text-slate-100">
          Audit missing vector chunks
        </h3>
        <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Checks local embedding rows against the active vector store and lists documents whose
          expected chunk vectors are missing or incomplete.
        </p>
        <div class="mt-4 flex items-center gap-3">
          <button
            class="rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-sm font-semibold text-rose-700 hover:border-rose-300 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-200"
            :disabled="missingVectorChunksLoading"
            @click="runMissingVectorChunkAudit"
          >
            <span v-if="missingVectorChunksLoading" class="inline-flex items-center gap-2">
              <Loader2 class="h-4 w-4 animate-spin" />
              Auditing...
            </span>
            <span v-else>Find affected docs</span>
          </button>
          <div v-if="missingVectorChunkAuditText" class="text-xs text-slate-500 dark:text-slate-400">
            {{ missingVectorChunkAuditText }}
          </div>
        </div>
        <div
          v-if="missingVectorChunkAudit"
          class="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-950/40 dark:text-slate-300"
        >
          <div class="font-semibold text-slate-700 dark:text-slate-200">
            Provider: {{ missingVectorChunkAudit.provider }}
          </div>
          <div class="mt-1">
            Scanned {{ missingVectorChunkAudit.scanned_docs }} docs, found
            {{ missingVectorChunkAudit.affected_docs }} affected
            ({{ missingVectorChunkAudit.fully_missing_docs }} fully missing,
            {{ missingVectorChunkAudit.partial_missing_docs }} partial).
          </div>
          <div
            v-if="missingVectorChunkAudit.items.length"
            class="mt-3 max-h-56 space-y-2 overflow-y-auto rounded border border-slate-200 bg-white p-2 dark:border-slate-700 dark:bg-slate-900"
          >
            <div
              v-for="item in missingVectorChunkAudit.items"
              :key="item.doc_id"
              class="rounded border border-slate-200 px-3 py-2 dark:border-slate-700"
            >
              <div class="font-semibold text-slate-800 dark:text-slate-100">
                #{{ item.doc_id }} {{ item.title || 'Untitled document' }}
              </div>
              <div class="mt-1 text-[11px] text-slate-500 dark:text-slate-400">
                source={{ item.embedding_source || 'unknown' }},
                found={{ item.found_vectors }}/{{ item.expected_vectors }},
                chunks={{ item.chunk_count }},
                state={{ item.fully_missing ? 'fully missing' : 'partial' }}
              </div>
            </div>
          </div>
          <div v-else class="mt-3 text-xs text-emerald-600 dark:text-emerald-300">
            No affected documents found.
          </div>
          <div
            v-if="missingVectorChunkAudit.truncated"
            class="mt-3 text-[11px] text-amber-700 dark:text-amber-300"
          >
            Showing the first {{ missingVectorChunkAudit.limit }} affected docs.
          </div>
        </div>
      </div>

      <div
        class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900"
      >
        <h3 class="text-lg font-semibold text-slate-900 dark:text-slate-100">Cleanup page texts</h3>
        <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Rebuilds `clean_text` + token estimates for all stored page texts.
        </p>
        <label class="mt-3 inline-flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
          <input v-model="cleanupClearFirst" type="checkbox" />
          Clear current clean fields first
        </label>
        <div class="mt-4 flex items-center gap-3">
          <button
            class="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
            :disabled="cleanupLoading"
            @click="confirmCleanupTexts"
          >
            <span v-if="cleanupLoading" class="inline-flex items-center gap-2">
              <Loader2 class="h-4 w-4 animate-spin" />
              Enqueuing...
            </span>
            <span v-else>Run cleanup</span>
          </button>
          <div v-if="cleanupResult" class="text-xs text-slate-500 dark:text-slate-400">
            {{ cleanupResult.queued ? `Queued ${cleanupResult.enqueued} docs` : `Updated ${cleanupResult.updated}/${cleanupResult.processed}` }}
          </div>
        </div>
      </div>
    </section>

    <section class="mt-6 grid gap-4 md:grid-cols-2">
      <div
        class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900"
      >
        <h3 class="text-lg font-semibold text-slate-900 dark:text-slate-100">
          Sync correspondents
        </h3>
        <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Pulls the full correspondent list from Paperless into the local cache.
        </p>
        <div class="mt-4 flex items-center gap-3">
          <button
            class="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
            :disabled="correspondentsSyncLoading"
            @click="syncCorrespondentsNow"
          >
            <span v-if="correspondentsSyncLoading" class="inline-flex items-center gap-2">
              <Loader2 class="h-4 w-4 animate-spin" />
              Syncing...
            </span>
            <span v-else>Sync correspondents</span>
          </button>
          <div
            v-if="correspondentsSyncResult"
            class="text-xs text-slate-500 dark:text-slate-400"
          >
            Upserted {{ correspondentsSyncResult.upserted }} / {{ correspondentsSyncResult.count }}
          </div>
        </div>
      </div>

      <div
        class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900"
      >
        <h3 class="text-lg font-semibold text-slate-900 dark:text-slate-100">Sync tags</h3>
        <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Pulls the full tag list from Paperless into the local cache.
        </p>
        <div class="mt-4 flex items-center gap-3">
          <button
            class="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
            :disabled="tagsSyncLoading"
            @click="syncTagsNow"
          >
            <span v-if="tagsSyncLoading" class="inline-flex items-center gap-2">
              <Loader2 class="h-4 w-4 animate-spin" />
              Syncing...
            </span>
            <span v-else>Sync tags</span>
          </button>
          <div v-if="tagsSyncResult" class="text-xs text-slate-500 dark:text-slate-400">
            Upserted {{ tagsSyncResult.upserted }} / {{ tagsSyncResult.count }}
          </div>
        </div>
      </div>
    </section>

    <MaintenanceRuntimeSection
      :worker-lock-status="workerLockStatus"
      :worker-lock-loading="workerLockLoading"
      :worker-lock-reset-loading="workerLockResetLoading"
      :worker-lock-status-ttl-label="workerLockStatusTtlLabel"
      :worker-lock-reset-result="workerLockResetResult"
      @refresh-lock="loadWorkerLockStatus"
      @reset-lock="confirmWorkerLockReset"
    />
  </section>

  <div
    v-if="showReprocessModal"
    class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4"
  >
    <div
      class="w-full max-w-xl rounded-2xl border border-rose-200 bg-white p-6 shadow-xl dark:border-rose-900/50 dark:bg-slate-900"
    >
      <div class="flex items-center justify-between">
        <div>
          <h3 class="text-lg font-semibold text-rose-700">Reprocess all documents?</h3>
          <p class="text-xs text-slate-500 dark:text-slate-400">
            This wipes all intelligence data (embeddings, suggestions, OCR layers) and rebuilds from
            scratch.
          </p>
        </div>
      </div>

      <div
        class="mt-4 rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-200"
      >
        This action cannot be undone. Paperless data is not modified.
      </div>

      <div
        v-if="syncStatus.status === 'running'"
        class="mt-4 rounded-lg border border-indigo-200 bg-indigo-50 p-3 text-xs text-indigo-700 dark:border-indigo-900/50 dark:bg-indigo-950/40 dark:text-indigo-200"
      >
        <div class="flex items-center gap-2">
          <Loader2 class="h-4 w-4 animate-spin" />
          Sync {{ syncStatus.processed }} / {{ syncStatus.total }} ({{ progressPercent }}%) - ETA
          {{ etaText }}
        </div>
      </div>

      <div class="mt-6 flex flex-wrap items-center justify-end gap-3">
        <button
          class="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
          :disabled="reprocessRunning"
          @click="closeReprocessModal"
        >
          Cancel
        </button>
        <button
          class="rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-rose-500"
          :disabled="syncing || isProcessing || reprocessRunning"
          @click="confirmReprocessAll"
        >
          <span v-if="reprocessRunning" class="inline-flex items-center gap-2">
            <Loader2 class="h-4 w-4 animate-spin" />
            Starting...
          </span>
          <span v-else>Yes, reprocess all</span>
        </button>
      </div>
    </div>
  </div>
  <div
    v-if="showClearAllModal"
    class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4"
  >
    <div
      class="w-full max-w-xl rounded-2xl border border-rose-300 bg-white p-6 shadow-xl dark:border-rose-900/60 dark:bg-slate-900"
    >
      <div class="flex items-center justify-between">
        <div>
          <h3 class="text-lg font-semibold text-rose-700">
            Wipe all local documents & intelligence data?
          </h3>
          <p class="text-xs text-slate-500 dark:text-slate-400">
            This removes every local document plus embeddings, suggestions, and vision OCR data.
          </p>
        </div>
      </div>

      <div
        class="mt-4 rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-200"
      >
        <strong>Warning:</strong> This cannot be undone. Paperless is not modified, so documents can
        reappear via sync.
      </div>

      <label
        class="mt-4 flex items-center gap-2 text-xs font-semibold text-rose-700 dark:text-rose-200"
      >
        <input
          v-model="clearAllArmed"
          type="checkbox"
          class="h-4 w-4 rounded border-rose-300 text-rose-600"
        />
        I understand this will permanently delete all local documents and intelligence data.
      </label>

      <div class="mt-6 flex flex-wrap items-center justify-end gap-3">
        <button
          class="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
          :disabled="clearAllLoading"
          @click="closeClearAllModal"
        >
          Cancel
        </button>
        <button
          class="rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-rose-500"
          :disabled="!clearAllArmed || clearAllLoading"
          @click="confirmClearAll"
        >
          <span v-if="clearAllLoading" class="inline-flex items-center gap-2">
            <Loader2 class="h-4 w-4 animate-spin" />
            Deleting...
          </span>
          <span v-else>Yes, wipe everything</span>
        </button>
      </div>
    </div>
  </div>
  <ConfirmDialog
    :open="confirmDialogOpen"
    :title="confirmDialogTitle"
    :message="confirmDialogMessage"
    confirm-label="Confirm"
    cancel-label="Cancel"
    @confirm="confirmDialogSubmit"
    @cancel="closeConfirmDialog"
  />
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Loader2, RefreshCcw } from 'lucide-vue-next'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import MaintenanceActionCard from '../components/MaintenanceActionCard.vue'
import MaintenanceRuntimeSection from '../components/MaintenanceRuntimeSection.vue'
import { useMaintenanceOps } from '../composables/useMaintenanceOps'
import type { QueueWorkerLockReset } from '../services/queue'
import { useToastStore } from '../stores/toastStore'

const toastStore = useToastStore()
const maintenanceOps = useMaintenanceOps()

const {
  syncStatus,
  embedStatus,
  workerLockStatus,
  workerLockLoading,
  reprocessRunning,
  visionLoading,
  suggestionsLoading,
  embeddingsLoading,
  similarityIndexLoading,
  missingVectorChunksLoading,
  clearAllLoading,
  cleanupLoading,
  correspondentsSyncLoading,
  tagsSyncLoading,
  workerLockResetLoading,
  loadWorkerLockStatus: fetchWorkerLockStatusNow,
  reprocessAll,
  removeVisionOcr,
  removeSuggestions,
  removeEmbeddings,
  removeSimilarityIndex,
  findMissingVectorChunks,
  clearAllIntelligence,
  cleanupTexts: runCleanupTexts,
  syncCorrespondentsNow: syncCorrespondentsAction,
  syncTagsNow: syncTagsAction,
  resetWorkerLockNow,
} = maintenanceOps

const showReprocessModal = ref(false)
const showClearAllModal = ref(false)
const clearAllArmed = ref(false)

const syncing = computed(
  () => syncStatus.value.status === 'running' || embedStatus.value.status === 'running',
)
const isProcessing = computed(
  () => syncStatus.value.status === 'running' || embedStatus.value.status === 'running',
)

const progressPercent = computed(() => {
  if (!syncStatus.value.total) return 0
  return Math.min(100, Math.round((syncStatus.value.processed / syncStatus.value.total) * 100))
})
const etaText = computed(() => {
  if (syncStatus.value.eta_seconds !== null && syncStatus.value.eta_seconds !== undefined) {
    const minutes = Math.floor(syncStatus.value.eta_seconds / 60)
    const seconds = syncStatus.value.eta_seconds % 60
    return `${minutes}:${seconds.toString().padStart(2, '0')}`
  }
  if (!syncStatus.value.started_at || !syncStatus.value.processed) return '--'
  const started = Date.parse(syncStatus.value.started_at)
  if (Number.isNaN(started)) return '--'
  const elapsedMs = Date.now() - started
  const rate = syncStatus.value.processed / Math.max(1, elapsedMs / 1000)
  if (!syncStatus.value.total || rate <= 0) return '--'
  const remaining = syncStatus.value.total - syncStatus.value.processed
  const etaSec = Math.max(0, Math.round(remaining / rate))
  const minutes = Math.floor(etaSec / 60)
  const seconds = etaSec % 60
  return `${minutes}:${seconds.toString().padStart(2, '0')}`
})

const visionResult = ref<{ deleted: number } | null>(null)
const suggestionsResult = ref<{ deleted: number } | null>(null)
const embeddingsResult = ref<{
  deleted: number
  qdrant_deleted: number
  qdrant_errors: number
} | null>(null)
const similarityIndexResult = ref<{
  deleted: number
  qdrant_deleted: number
  qdrant_errors: number
} | null>(null)
const missingVectorChunkAudit = ref<{
  provider: string
  scanned_docs: number
  affected_docs: number
  fully_missing_docs: number
  partial_missing_docs: number
  limit: number
  truncated: boolean
  items: Array<{
    doc_id: number
    title?: string | null
    embedding_source?: string | null
    chunk_count: number
    expected_vectors: number
    found_vectors: number
    fully_missing: boolean
    embedded_at?: string | null
  }>
} | null>(null)
const visionResultText = computed(() =>
  visionResult.value ? `Removed ${visionResult.value.deleted} rows` : '',
)
const suggestionsResultText = computed(() =>
  suggestionsResult.value ? `Removed ${suggestionsResult.value.deleted} rows` : '',
)
const embeddingsResultText = computed(() =>
  embeddingsResult.value
    ? `Removed ${embeddingsResult.value.deleted} rows (Qdrant ok: ${embeddingsResult.value.qdrant_deleted}, errors: ${embeddingsResult.value.qdrant_errors})`
    : '',
)
const similarityIndexResultText = computed(() =>
  similarityIndexResult.value
    ? `Reset ${similarityIndexResult.value.deleted} task-runs (Qdrant ok: ${similarityIndexResult.value.qdrant_deleted}, errors: ${similarityIndexResult.value.qdrant_errors})`
    : '',
)
const missingVectorChunkAuditText = computed(() =>
  missingVectorChunkAudit.value
    ? `${missingVectorChunkAudit.value.affected_docs} affected docs (${missingVectorChunkAudit.value.fully_missing_docs} fully missing)`
    : '',
)
const clearAllResult = ref<{
  cleared_documents: number
  cleared_embeddings: number
  cleared_page_texts: number
  cleared_suggestions: number
  qdrant_deleted: number
  qdrant_errors: number
} | null>(null)

const correspondentsSyncResult = ref<{ count: number; upserted: number } | null>(null)
const tagsSyncResult = ref<{ count: number; upserted: number } | null>(null)
const workerLockResetResult = ref<QueueWorkerLockReset | null>(null)
const cleanupClearFirst = ref(false)
const cleanupResult = ref<{
  queued: boolean
  docs: number
  enqueued: number
  processed: number
  updated: number
} | null>(null)

const confirmDialogOpen = ref(false)
const confirmDialogTitle = ref('')
const confirmDialogMessage = ref('')
const confirmDialogAction = ref<null | (() => Promise<void>)>(null)

const openConfirmDialog = (title: string, message: string, action: () => Promise<void>) => {
  confirmDialogTitle.value = title
  confirmDialogMessage.value = message
  confirmDialogAction.value = action
  confirmDialogOpen.value = true
}

const closeConfirmDialog = () => {
  confirmDialogOpen.value = false
  confirmDialogAction.value = null
}

const confirmDialogSubmit = async () => {
  if (!confirmDialogAction.value) return
  const action = confirmDialogAction.value
  closeConfirmDialog()
  await action()
}

const workerLockStatusTtlLabel = computed(() => {
  const ttl = workerLockStatus.value?.ttl_seconds
  if (ttl === null || ttl === undefined) return 'n/a'
  if (ttl <= 0) return 'expired'
  return `${ttl}s`
})

const openReprocessModal = () => {
  showReprocessModal.value = true
}

const closeReprocessModal = () => {
  showReprocessModal.value = false
}

const confirmReprocessAll = async () => {
  try {
    await reprocessAll()
    showReprocessModal.value = false
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to start reprocess'
    toastStore.push(message, 'danger', 'Error')
  }
}

const confirmVision = async () => {
  openConfirmDialog(
    'Remove Vision OCR',
    'Remove all vision OCR pages for every document? This cannot be undone.',
    async () => {
      visionResult.value = null
      try {
        const result = await removeVisionOcr()
        visionResult.value = { deleted: result.deleted ?? 0 }
        toastStore.push('Vision OCR removed', 'success', 'Completed')
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to remove vision OCR'
        toastStore.push(message, 'danger', 'Error')
      }
    },
  )
}

const confirmSuggestions = async () => {
  openConfirmDialog(
    'Remove AI suggestions',
    'Remove all AI suggestions for every document? This cannot be undone.',
    async () => {
      suggestionsResult.value = null
      try {
        const result = await removeSuggestions()
        suggestionsResult.value = { deleted: result.deleted ?? 0 }
        toastStore.push('Suggestions removed', 'success', 'Completed')
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to remove suggestions'
        toastStore.push(message, 'danger', 'Error')
      }
    },
  )
}

const confirmEmbeddings = async () => {
  openConfirmDialog(
    'Remove embeddings',
    'Remove all embeddings (paperless + vision) for every document? This cannot be undone.',
    async () => {
      embeddingsResult.value = null
      try {
        const result = await removeEmbeddings()
        embeddingsResult.value = {
          deleted: result.deleted ?? 0,
          qdrant_deleted: result.qdrant_deleted ?? 0,
          qdrant_errors: result.qdrant_errors ?? 0,
        }
        toastStore.push('Embeddings removed', 'success', 'Completed')
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to remove embeddings'
        toastStore.push(message, 'danger', 'Error')
      }
    },
  )
}

const confirmSimilarityIndex = async () => {
  openConfirmDialog(
    'Reset similarity index',
    'Delete all doc-level similarity vectors and similarity task history? You can rebuild via Continue missing processing.',
    async () => {
      similarityIndexResult.value = null
      try {
        const result = await removeSimilarityIndex()
        similarityIndexResult.value = {
          deleted: result.deleted ?? 0,
          qdrant_deleted: result.qdrant_deleted ?? 0,
          qdrant_errors: result.qdrant_errors ?? 0,
        }
        toastStore.push('Similarity index reset', 'success', 'Completed')
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to reset similarity index'
        toastStore.push(message, 'danger', 'Error')
      }
    },
  )
}

const runMissingVectorChunkAudit = async () => {
  missingVectorChunkAudit.value = null
  try {
    const result = await findMissingVectorChunks()
    missingVectorChunkAudit.value = result
    if (result.affected_docs > 0) {
      toastStore.push(
        `Found ${result.affected_docs} docs with missing active vector chunks`,
        'warning',
        'Audit complete',
      )
    } else {
      toastStore.push('No missing active vector chunks found', 'success', 'Audit complete')
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to audit missing vector chunks'
    toastStore.push(message, 'danger', 'Error')
  }
}

const confirmCleanupTexts = async () => {
  openConfirmDialog(
    'Cleanup page texts',
    'Recompute cleaned text/token fields for all stored pages?',
    async () => {
      cleanupResult.value = null
      try {
        const result = await runCleanupTexts({
          clear_first: cleanupClearFirst.value,
          enqueue: true,
        })
        cleanupResult.value = result
        toastStore.push('Cleanup queued', 'success', 'Completed')
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to run cleanup'
        toastStore.push(message, 'danger', 'Error')
      }
    },
  )
}

const syncCorrespondentsNow = async () => {
  correspondentsSyncResult.value = null
  try {
    const result = await syncCorrespondentsAction()
    correspondentsSyncResult.value = {
      count: result.count ?? 0,
      upserted: result.upserted ?? 0,
    }
    toastStore.push('Correspondents synced', 'success', 'Sync complete')
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to sync correspondents'
    toastStore.push(message, 'danger', 'Error')
  }
}

const syncTagsNow = async () => {
  tagsSyncResult.value = null
  try {
    const result = await syncTagsAction()
    tagsSyncResult.value = {
      count: result.count ?? 0,
      upserted: result.upserted ?? 0,
    }
    toastStore.push('Tags synced', 'success', 'Sync complete')
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to sync tags'
    toastStore.push(message, 'danger', 'Error')
  }
}

const loadWorkerLockStatus = async () => {
  try {
    await fetchWorkerLockStatusNow()
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to load worker lock status'
    toastStore.push(message, 'danger', 'Error')
  }
}

const confirmWorkerLockReset = async () => {
  openConfirmDialog(
    'Reset worker lock',
    'Reset Redis worker lock now? Use this only if a stale lock blocks worker startup.',
    async () => {
      workerLockResetResult.value = null
      try {
        const result = await resetWorkerLockNow()
        workerLockResetResult.value = result
        await loadWorkerLockStatus()
        if (result.reason === 'worker_active') {
          toastStore.push('Active worker detected; lock was not reset.', 'info', 'Skipped')
        } else {
          toastStore.push('Worker lock reset request completed', 'success', 'Completed')
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to reset worker lock'
        toastStore.push(message, 'danger', 'Error')
      }
    },
  )
}

onMounted(async () => {
  await loadWorkerLockStatus()
})

const openClearAllModal = () => {
  clearAllArmed.value = false
  showClearAllModal.value = true
}

const closeClearAllModal = () => {
  showClearAllModal.value = false
}

const confirmClearAll = async () => {
  clearAllResult.value = null
  try {
    const result = await clearAllIntelligence()
    clearAllResult.value = {
      cleared_documents: result.cleared_documents ?? 0,
      cleared_embeddings: result.cleared_embeddings ?? 0,
      cleared_page_texts: result.cleared_page_texts ?? 0,
      cleared_suggestions: result.cleared_suggestions ?? 0,
      qdrant_deleted: result.qdrant_deleted ?? 0,
      qdrant_errors: result.qdrant_errors ?? 0,
    }
    showClearAllModal.value = false
    toastStore.push('Local data wiped', 'success', 'Completed')
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to wipe local data'
    toastStore.push(message, 'danger', 'Error')
  }
}
</script>
