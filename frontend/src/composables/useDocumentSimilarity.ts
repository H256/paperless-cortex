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
  let requestToken = 0

  const loadSimilarity = async (params?: { similarMinScore?: number; duplicateThreshold?: number }) => {
    const token = ++requestToken
    const minScoreRaw = Number(params?.similarMinScore ?? 0.5)
    const duplicateRaw = Number(params?.duplicateThreshold ?? 0.92)
    const minScore = Number.isFinite(minScoreRaw) ? Math.min(1, Math.max(0.5, minScoreRaw)) : 0.5
    const duplicate = Number.isFinite(duplicateRaw) ? Math.min(1, Math.max(0.8, duplicateRaw)) : 0.92
    loading.value = true
    error.value = ''
    try {
      const [similarResponse, duplicateResponse] = await Promise.all([
        unwrap<SimilarDocumentsResponse>(
          getSimilarDocumentsDocumentsDocIdSimilarGet(docId(), {
            top_k: 10,
            min_score: minScore,
          }),
        ),
        unwrap<SimilarDocumentsResponse>(
          getDuplicateDocumentsDocumentsDocIdDuplicatesGet(docId(), {
            threshold: duplicate,
            top_k: 10,
          }),
        ),
      ])
      if (token !== requestToken) return
      similarMatches.value = normalizeMatches(similarResponse)
      duplicateMatches.value = normalizeMatches(duplicateResponse)
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
    error.value = ''
    loading.value = false
  }

  return { similarMatches, duplicateMatches, loading, error, loadSimilarity, reset }
}
