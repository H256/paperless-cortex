import { ref } from 'vue'
import { getTextCandidates } from '../services/documents'
import type { TextCandidatesResponse } from '../api/generated/model'

/**
 * Deterministic date/correspondent candidates computed from the document text.
 * The request is read-only on the backend (no OCR, LLM or queue work), so it is
 * safe to load whenever the suggestions tab is shown.
 */
export const useTextCandidates = () => {
  const candidates = ref<TextCandidatesResponse | null>(null)
  const loading = ref(false)
  const error = ref('')
  let token = 0

  const load = async (docId: number) => {
    const current = ++token
    loading.value = true
    error.value = ''
    try {
      const data = await getTextCandidates(docId)
      if (current !== token) return
      candidates.value = data
    } catch (err: unknown) {
      if (current !== token) return
      candidates.value = null
      error.value = err instanceof Error ? err.message : 'Failed to load text candidates'
    } finally {
      if (current === token) loading.value = false
    }
  }

  const reset = () => {
    token += 1
    candidates.value = null
    error.value = ''
    loading.value = false
  }

  return { candidates, loading, error, load, reset }
}
