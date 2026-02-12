import { computed, type Ref } from 'vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import {
  continueDocumentPipeline,
  getDocumentPipelineStatus,
  type ContinuePipelinePayload,
} from '../services/documents'

const keyFor = (docId: number) => ['document-pipeline-status', docId] as const

export const useDocumentPipeline = (docId: Ref<number>) => {
  const queryClient = useQueryClient()
  const queryKey = computed(() => keyFor(docId.value))

  const statusQuery = useQuery({
    queryKey,
    queryFn: () => getDocumentPipelineStatus(docId.value),
    staleTime: 15_000,
    enabled: computed(() => Number.isFinite(docId.value) && docId.value > 0),
  })

  const continueMutation = useMutation({
    mutationFn: (payload: ContinuePipelinePayload = {}) => continueDocumentPipeline(docId.value, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKey.value })
    },
  })

  return {
    pipelineStatus: statusQuery.data,
    pipelineStatusLoading: statusQuery.isPending,
    pipelineStatusError: computed(() => {
      const err = statusQuery.error.value
      if (!err) return ''
      return err instanceof Error ? err.message : String(err)
    }),
    refreshPipelineStatus: statusQuery.refetch,
    continuePipeline: continueMutation.mutateAsync,
    continuePipelineLoading: continueMutation.isPending,
  }
}
