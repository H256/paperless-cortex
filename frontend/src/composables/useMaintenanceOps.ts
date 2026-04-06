import { computed } from 'vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import {
  cleanupTexts,
  clearIntelligence,
  deleteEmbeddings,
  findMissingVectorChunks,
  deleteSimilarityIndex,
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
  type MissingVectorChunkAuditResult,
  type SyncStatus,
} from '../services/documents'
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

  const removeSimilarityIndexMutation = useMutation({
    mutationFn: () => deleteSimilarityIndex(),
    onSuccess: async () => invalidateProcessingQueries(queryClient),
  })

  const missingVectorChunksMutation = useMutation<MissingVectorChunkAuditResult, Error, { limit?: number }>({
    mutationFn: ({ limit }) => findMissingVectorChunks(limit ?? 100),
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
    workerLockStatus: computed(() => workerLockQuery.data.value ?? null),
    workerLockLoading: computed(() => workerLockQuery.isFetching.value),
    reprocessRunning: computed(() => reprocessMutation.isPending.value),
    visionLoading: computed(() => removeVisionMutation.isPending.value),
    suggestionsLoading: computed(() => removeSuggestionsMutation.isPending.value),
    embeddingsLoading: computed(() => removeEmbeddingsMutation.isPending.value),
    similarityIndexLoading: computed(() => removeSimilarityIndexMutation.isPending.value),
    missingVectorChunksLoading: computed(() => missingVectorChunksMutation.isPending.value),
    clearAllLoading: computed(() => clearAllMutation.isPending.value),
    cleanupLoading: computed(() => cleanupMutation.isPending.value),
    correspondentsSyncLoading: computed(() => syncCorrespondentsMutation.isPending.value),
    tagsSyncLoading: computed(() => syncTagsMutation.isPending.value),
    workerLockResetLoading: computed(() => resetWorkerLockMutation.isPending.value),
    loadWorkerLockStatus,
    refreshPipelineStatus,
    reprocessAll: async () => reprocessMutation.mutateAsync(),
    removeVisionOcr: async () => removeVisionMutation.mutateAsync(),
    removeSuggestions: async () => removeSuggestionsMutation.mutateAsync(),
    removeEmbeddings: async () => removeEmbeddingsMutation.mutateAsync(),
    removeSimilarityIndex: async () => removeSimilarityIndexMutation.mutateAsync(),
    findMissingVectorChunks: async (limit = 100) =>
      missingVectorChunksMutation.mutateAsync({ limit }),
    clearAllIntelligence: async () => clearAllMutation.mutateAsync(),
    cleanupTexts: async (payload: CleanupTextsPayload) => cleanupMutation.mutateAsync(payload),
    syncCorrespondentsNow: async () => syncCorrespondentsMutation.mutateAsync(),
    syncTagsNow: async () => syncTagsMutation.mutateAsync(),
    resetWorkerLockNow: async (force = false) => resetWorkerLockMutation.mutateAsync({ force }),
  }
}
