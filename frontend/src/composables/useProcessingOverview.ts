import { computed } from 'vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import {
  cancelEmbeddings,
  cancelSync,
  getEmbedStatus,
  getStats,
  getSyncStatus,
  type DocumentStats,
  type EmbedStatus,
  type SyncStatus,
} from '../services/documents'
import { clearQueue, fetchQueueStatus } from '../services/queue'

const EMPTY_SYNC: SyncStatus = {
  status: 'idle',
  processed: 0,
  total: 0,
  started_at: null,
  eta_seconds: null,
}

const EMPTY_EMBED: EmbedStatus = {
  status: 'idle',
  processed: 0,
  total: 0,
  started_at: null,
  eta_seconds: null,
}

const EMPTY_STATS: DocumentStats = {
  total: 0,
  processed: 0,
  unprocessed: 0,
  embeddings: 0,
  vision: 0,
  suggestions: 0,
  fully_processed: 0,
}

export const useProcessingOverview = () => {
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

  const statsQuery = useQuery({
    queryKey: ['documents-stats'],
    queryFn: () => getStats(),
    refetchInterval: 30_000,
    staleTime: 10_000,
  })

  const queueStatusQuery = useQuery({
    queryKey: ['queue-status'],
    queryFn: () => fetchQueueStatus(),
    refetchInterval: 30_000,
    staleTime: 5_000,
  })

  const clearQueueMutation = useMutation({
    mutationFn: () => clearQueue(),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['queue-status'] })
    },
  })

  const cancelMutation = useMutation({
    mutationFn: async () => {
      await cancelSync()
      await cancelEmbeddings()
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['sync-status'] }),
        queryClient.invalidateQueries({ queryKey: ['embed-status'] }),
      ])
    },
  })

  const refresh = async () =>
    Promise.all([
      syncStatusQuery.refetch(),
      embedStatusQuery.refetch(),
      statsQuery.refetch(),
      queueStatusQuery.refetch(),
    ])

  return {
    syncStatus: computed(() => syncStatusQuery.data.value ?? EMPTY_SYNC),
    embedStatus: computed(() => embedStatusQuery.data.value ?? EMPTY_EMBED),
    stats: computed(() => statsQuery.data.value ?? EMPTY_STATS),
    queueStatus: computed(() => queueStatusQuery.data.value ?? { enabled: false, length: null }),
    lastSynced: computed(() => syncStatusQuery.data.value?.last_synced_at ?? null),
    refresh,
    clearQueueNow: () => clearQueueMutation.mutateAsync(),
    cancelSyncAndEmbeddings: () => cancelMutation.mutateAsync(),
  }
}
