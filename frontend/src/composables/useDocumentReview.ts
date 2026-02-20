import { computed, type Ref } from 'vue'
import { useMutation, useQueryClient } from '@tanstack/vue-query'
import { markDocumentReviewed, type MarkReviewedResult } from '../services/documents'

export const useDocumentReview = (docId: Ref<number>) => {
  const queryClient = useQueryClient()

  const markReviewedMutation = useMutation({
    mutationFn: () => markDocumentReviewed(docId.value),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['documents-list'] }),
        queryClient.invalidateQueries({ queryKey: ['dashboard-data'] }),
      ])
    },
  })

  return {
    reviewMarking: computed(() => markReviewedMutation.isPending.value),
    markReviewed: async (): Promise<MarkReviewedResult> => markReviewedMutation.mutateAsync(),
  }
}
