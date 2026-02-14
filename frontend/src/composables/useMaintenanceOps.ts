import { computed } from 'vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import {
  cleanupTexts,
  clearIntelligence,
  deleteEmbeddings,
  deleteSuggestions,
  deleteVisionOcr,
  getEmbedStatus,
  getSyncStatus,
  processMissing,
  resetIntelligence,
  syncCorrespondents,
  syncDocuments,
  syncTags,
  type CleanupTextsPayload,
  type EmbedStatus,
  type SyncStatus,
} from '../services/documents'
import { fetchHealthStatus } from '../services/status'
import {
  fetchWorkerLockStatus,
  resetWorkerLock,
  type QueueWorkerLockReset,
  type QueueWorkerLockStatus,
} from '../services/queue'

const IDLE_SYNC_STATUS: SyncStatus = {
  status: 'idle',
  processed: 0,
  total: 0,
  started_at: null,
  eta_seconds: null,
}

const IDLE_EMBED_STATUS: EmbedStatus = {
  status: 'idle',
  processed: 0,
  total: 0,
  started_at: null,
  eta_seconds: null,
}

const EMPTY_RUNTIME = {
  paperless_base_url: '',
  llm_base_url: '',
  qdrant_url: '',
  redis_host: '',
  text_model: '',
  embedding_model: '',
  vision_model: '',
  evidence_max_pages: 0,
  evidence_min_snippet_chars: 0,
}

const REPROCESS_SYNC_PARAMS = {
  page_size: 200,
  incremental: false,
  page: 1,
  page_only: false,
  embed: false,
  force_embed: false,
  mark_missing: true,
}

const invalidateProcessingQueries = async (queryClient: ReturnType<typeof useQueryClient>) =>
  Promise.all([
    queryClient.invalidateQueries({ queryKey: ['sync-status'] }),
    queryClient.invalidateQueries({ queryKey: ['embed-status'] }),
    queryClient.invalidateQueries({ queryKey: ['dashboard-data'] }),
    queryClient.invalidateQueries({ queryKey: ['documents-list'] }),
    queryClient.invalidateQueries({ queryKey: ['queue-status'] }),
    queryClient.invalidateQueries({ queryKey: ['queue-running'] }),
    queryClient.invalidateQueries({ queryKey: ['queue-peek'] }),
  ])

export const useMaintenanceOps = () => {
  const queryClient = useQueryClient()

  const syncStatusQuery = useQuery({
    queryKey: ['sync-status'],
    queryFn: () => getSyncStatus(),
    refetchInterval: 30_000,
    staleTime: 5_000,
  })

  const embedStatusQuery = useQuery({
    queryKey: ['embed-status'],
    queryFn: () => getEmbedStatus(),
    refetchInterval: 30_000,
    staleTime: 5_000,
  })

  const runtimeQuery = useQuery({
    queryKey: ['runtime-status'],
    queryFn: () => fetchHealthStatus(),
    staleTime: 60_000,
  })

  const workerLockQuery = useQuery({
    queryKey: ['worker-lock-status'],
    queryFn: () => fetchWorkerLockStatus(),
    staleTime: 5_000,
  })

  const reprocessMutation = useMutation({
    mutationFn: async () => {
      await syncDocuments(REPROCESS_SYNC_PARAMS)
      await resetIntelligence()
      return processMissing()
    },
    onSuccess: async () => invalidateProcessingQueries(queryClient),
  })

  const removeVisionMutation = useMutation({
    mutationFn: () => deleteVisionOcr(),
    onSuccess: async () => invalidateProcessingQueries(queryClient),
  })

  const removeSuggestionsMutation = useMutation({
    mutationFn: () => deleteSuggestions(),
    onSuccess: async () => invalidateProcessingQueries(queryClient),
  })

  const removeEmbeddingsMutation = useMutation({
    mutationFn: () => deleteEmbeddings(),
    onSuccess: async () => invalidateProcessingQueries(queryClient),
  })

  const clearAllMutation = useMutation({
    mutationFn: () => clearIntelligence(),
    onSuccess: async () => invalidateProcessingQueries(queryClient),
  })

  const cleanupMutation = useMutation({
    mutationFn: (payload: CleanupTextsPayload) => cleanupTexts(payload),
    onSuccess: async () => invalidateProcessingQueries(queryClient),
  })

  const syncCorrespondentsMutation = useMutation({
    mutationFn: () => syncCorrespondents(),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ['documents-meta'] }),
  })

  const syncTagsMutation = useMutation({
    mutationFn: () => syncTags(),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ['documents-meta'] }),
  })

  const resetWorkerLockMutation = useMutation<QueueWorkerLockReset, Error, { force?: boolean }>({
    mutationFn: ({ force }) => resetWorkerLock(force),
    onSuccess: async () => {
      await workerLockQuery.refetch()
    },
  })

  const refreshPipelineStatus = async () =>
    Promise.all([syncStatusQuery.refetch(), embedStatusQuery.refetch()])

  const loadWorkerLockStatus = async (): Promise<QueueWorkerLockStatus | null> => {
    const result = await workerLockQuery.refetch()
    return result.data ?? null
  }

  return {
    syncStatus: computed(() => syncStatusQuery.data.value ?? IDLE_SYNC_STATUS),
    embedStatus: computed(() => embedStatusQuery.data.value ?? IDLE_EMBED_STATUS),
    runtime: computed(() => runtimeQuery.data.value ?? EMPTY_RUNTIME),
    workerLockStatus: computed(() => workerLockQuery.data.value ?? null),
    workerLockLoading: computed(() => workerLockQuery.isFetching.value),
    reprocessRunning: computed(() => reprocessMutation.isPending.value),
    visionLoading: computed(() => removeVisionMutation.isPending.value),
    suggestionsLoading: computed(() => removeSuggestionsMutation.isPending.value),
    embeddingsLoading: computed(() => removeEmbeddingsMutation.isPending.value),
    clearAllLoading: computed(() => clearAllMutation.isPending.value),
    cleanupLoading: computed(() => cleanupMutation.isPending.value),
    correspondentsSyncLoading: computed(() => syncCorrespondentsMutation.isPending.value),
    tagsSyncLoading: computed(() => syncTagsMutation.isPending.value),
    workerLockResetLoading: computed(() => resetWorkerLockMutation.isPending.value),
    refreshPipelineStatus,
    loadWorkerLockStatus,
    refreshRuntime: async () => runtimeQuery.refetch(),
    reprocessAll: async () => reprocessMutation.mutateAsync(),
    removeVisionOcr: async () => removeVisionMutation.mutateAsync(),
    removeSuggestions: async () => removeSuggestionsMutation.mutateAsync(),
    removeEmbeddings: async () => removeEmbeddingsMutation.mutateAsync(),
    clearAllIntelligence: async () => clearAllMutation.mutateAsync(),
    cleanupTexts: async (payload: CleanupTextsPayload) => cleanupMutation.mutateAsync(payload),
    syncCorrespondentsNow: async () => syncCorrespondentsMutation.mutateAsync(),
    syncTagsNow: async () => syncTagsMutation.mutateAsync(),
    resetWorkerLockNow: async (force = false) => resetWorkerLockMutation.mutateAsync({ force }),
  }
}
