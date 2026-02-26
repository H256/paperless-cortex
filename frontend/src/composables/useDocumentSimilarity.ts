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

  const loadSimilarity = async (params?: { similarMinScore?: number; duplicateThreshold?: number }) => {
    const minScoreRaw = Number(params?.similarMinScore ?? 0.5)
    const duplicateRaw = Number(params?.duplicateThreshold ?? 0.92)
    const minScore = Number.isFinite(minScoreRaw) ? Math.min(1, Math.max(0.5, minScoreRaw)) : 0.5
    const duplicate = Number.isFinite(duplicateRaw) ? Math.min(1, Math.max(0.8, duplicateRaw)) : 0.92
    await Promise.all([
      queryClient.fetchQuery({
        queryKey: ['documents', 'similar', docId(), minScore],
        queryFn: () =>
          unwrap<SimilarDocumentsResponse>(
            getSimilarDocumentsDocumentsDocIdSimilarGet(docId(), {
              top_k: 10,
              min_score: minScore,
            }),
          ),
      }),
      queryClient.fetchQuery({
        queryKey: ['documents', 'duplicates', docId(), duplicate],
        queryFn: () =>
          unwrap<SimilarDocumentsResponse>(
            getDuplicateDocumentsDocumentsDocIdDuplicatesGet(docId(), {
              threshold: duplicate,
              top_k: 10,
            }),
          ),
      }),
    ])
    const similarData = queryClient.getQueryData<SimilarDocumentsResponse>([
      'documents',
      'similar',
      docId(),
      minScore,
    ])
    const duplicateData = queryClient.getQueryData<SimilarDocumentsResponse>([
      'documents',
      'duplicates',
      docId(),
      duplicate,
    ])
    if (similarData) {
      queryClient.setQueryData(['documents', 'similar', docId()], similarData)
    }
    if (duplicateData) {
      queryClient.setQueryData(['documents', 'duplicates', docId()], duplicateData)
    }
  }

  const reset = () => {
    queryClient.removeQueries({ queryKey: ['documents', 'similar', docId()] })
    queryClient.removeQueries({ queryKey: ['documents', 'duplicates', docId()] })
  }

  return { similarMatches, duplicateMatches, loading, error, loadSimilarity, reset }
}
