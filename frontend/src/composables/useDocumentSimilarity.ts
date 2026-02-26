import { computed } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { unwrap } from '../api/orval'
import {
  getSimilarDocumentsDocumentsDocIdSimilarGet,
  getDuplicateDocumentsDocumentsDocIdDuplicatesGet,
} from '../api/generated/client'
import type { SimilarDocumentMatch, SimilarDocumentsResponse } from '../api/generated/model'

const errorMessage = (err: unknown, fallback: string) => {
  if (err instanceof Error) return err.message || fallback
  if (typeof err === 'string') return err || fallback
  return fallback
}

type SimilarMatchWithDocument = SimilarDocumentMatch & {
  document: NonNullable<SimilarDocumentMatch['document']>
}

const hasDocument = (match: SimilarDocumentMatch): match is SimilarMatchWithDocument =>
  Boolean(match.document)

const normalizeMatches = (data?: SimilarDocumentsResponse | null): SimilarMatchWithDocument[] =>
  (data?.matches || []).filter(hasDocument)

export const useDocumentSimilarity = (docId: () => number) => {
  const queryClient = useQueryClient()
  const similarQuery = useQuery({
    queryKey: computed(() => ['documents', 'similar', docId()]),
    queryFn: () =>
      unwrap<SimilarDocumentsResponse>(
        getSimilarDocumentsDocumentsDocIdSimilarGet(docId(), { top_k: 10 }),
      ),
    enabled: false,
  })
  const duplicateQuery = useQuery({
    queryKey: computed(() => ['documents', 'duplicates', docId()]),
    queryFn: () =>
      unwrap<SimilarDocumentsResponse>(
        getDuplicateDocumentsDocumentsDocIdDuplicatesGet(docId(), { threshold: 0.92, top_k: 10 }),
      ),
    enabled: false,
  })

  const similarMatches = computed(() => normalizeMatches(similarQuery.data.value || null))
  const duplicateMatches = computed(() => normalizeMatches(duplicateQuery.data.value || null))
  const loading = computed(() => similarQuery.isFetching.value || duplicateQuery.isFetching.value)
  const error = computed(() => {
    if (similarQuery.error.value) return errorMessage(similarQuery.error.value, 'Failed to load similar documents')
    if (duplicateQuery.error.value) return errorMessage(duplicateQuery.error.value, 'Failed to load duplicates')
    return ''
  })

  const loadSimilarity = async () => {
    await Promise.all([similarQuery.refetch(), duplicateQuery.refetch()])
  }

  const reset = () => {
    queryClient.removeQueries({ queryKey: ['documents', 'similar', docId()] })
    queryClient.removeQueries({ queryKey: ['documents', 'duplicates', docId()] })
  }

  return { similarMatches, duplicateMatches, loading, error, loadSimilarity, reset }
}
