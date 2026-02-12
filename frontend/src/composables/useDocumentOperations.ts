import { computed, type Ref } from 'vue'
import { useMutation, useQueryClient } from '@tanstack/vue-query'
import {
  cleanupTexts,
  enqueueDocumentTask,
  resetAndReprocessDocument,
  type DocumentOperationTaskPayload,
} from '../services/documents'

export const useDocumentOperations = (docId: Ref<number>) => {
  const queryClient = useQueryClient()

  const invalidateRelated = async () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: ['queue-status'] }),
      queryClient.invalidateQueries({ queryKey: ['queue-running'] }),
      queryClient.invalidateQueries({ queryKey: ['queue-peek'] }),
      queryClient.invalidateQueries({ queryKey: ['document-pipeline-status', docId.value] }),
    ])

  const enqueueTaskMutation = useMutation({
    mutationFn: (payload: DocumentOperationTaskPayload) => enqueueDocumentTask(docId.value, payload),
    onSuccess: invalidateRelated,
  })

  const cleanupMutation = useMutation({
    mutationFn: (clearFirst: boolean) =>
      cleanupTexts({
        doc_ids: [docId.value],
        clear_first: clearFirst,
        enqueue: true,
      }),
    onSuccess: invalidateRelated,
  })

  const resetMutation = useMutation({
    mutationFn: (enqueue: boolean) => resetAndReprocessDocument(docId.value, enqueue),
    onSuccess: invalidateRelated,
  })

  const loading = computed(
    () =>
      enqueueTaskMutation.isPending.value ||
      cleanupMutation.isPending.value ||
      resetMutation.isPending.value,
  )

  return {
    loading,
    enqueueTask: enqueueTaskMutation.mutateAsync,
    cleanup: cleanupMutation.mutateAsync,
    resetAndReprocess: (enqueue = true) => resetMutation.mutateAsync(enqueue),
  }
}
