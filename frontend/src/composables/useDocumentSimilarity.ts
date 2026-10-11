import { ref } from 'vue'
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
  const similarMatches = ref<SimilarMatchWithDocument[]>([])
  const duplicateMatches = ref<SimilarMatchWithDocument[]>([])
  const loading = ref(false)
  const error = ref('')
  const hiddenReviewed = ref(0)
  let requestToken = 0

  const loadSimilarity = async (params?: {
    similarMinScore?: number
    duplicateThreshold?: number
    excludeReviewed?: boolean
  }) => {
    const token = ++requestToken
    const minScoreRaw = Number(params?.similarMinScore ?? 0.5)
    const duplicateRaw = Number(params?.duplicateThreshold ?? 0.92)
    const minScore = Number.isFinite(minScoreRaw) ? Math.min(1, Math.max(0.5, minScoreRaw)) : 0.5
    const duplicate = Number.isFinite(duplicateRaw) ? Math.min(1, Math.max(0.8, duplicateRaw)) : 0.92
    const excludeReviewed = Boolean(params?.excludeReviewed)
    loading.value = true
    error.value = ''
    try {
      const [similarResponse, duplicateResponse] = await Promise.all([
        unwrap<SimilarDocumentsResponse>(
          getSimilarDocumentsDocumentsDocIdSimilarGet(docId(), {
            top_k: 10,
            min_score: minScore,
            exclude_reviewed: excludeReviewed,
          }),
        ),
        unwrap<SimilarDocumentsResponse>(
          getDuplicateDocumentsDocumentsDocIdDuplicatesGet(docId(), {
            threshold: duplicate,
            top_k: 10,
            exclude_reviewed: excludeReviewed,
          }),
        ),
      ])
      if (token !== requestToken) return
      similarMatches.value = normalizeMatches(similarResponse)
      duplicateMatches.value = normalizeMatches(duplicateResponse)
      hiddenReviewed.value = Math.max(
        similarResponse?.hidden_reviewed ?? 0,
        duplicateResponse?.hidden_reviewed ?? 0,
      )
    } catch (err: unknown) {
      if (token !== requestToken) return
      error.value = errorMessage(err, 'Failed to load similarity results')
    } finally {
      if (token === requestToken) {
        loading.value = false
      }
    }
  }

  const reset = () => {
    requestToken += 1
    similarMatches.value = []
    duplicateMatches.value = []
    hiddenReviewed.value = 0
    error.value = ''
    loading.value = false
  }

  return {
    similarMatches,
    duplicateMatches,
    hiddenReviewed,
    loading,
    error,
    loadSimilarity,
    reset,
  }
}
