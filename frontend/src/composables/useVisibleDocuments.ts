import { computed, type Ref } from 'vue'
import type { DocumentRow } from '../services/documents'

export const useVisibleDocuments = (
  documents: Ref<DocumentRow[]>,
  analysisFilter: Ref<'all' | 'analyzed' | 'not_analyzed'>,
  modelFilter: Ref<string>,
) => {
  const hasDerived = (doc: DocumentRow) =>
    Boolean(doc.has_embeddings || doc.has_suggestions || doc.has_vision_pages)

  const visibleDocuments = computed(() => {
    let filtered = documents.value
    if (analysisFilter.value !== 'all') {
      const shouldBeAnalyzed = analysisFilter.value === 'analyzed'
      filtered = filtered.filter((doc) => hasDerived(doc) === shouldBeAnalyzed)
    }
    const needle = modelFilter.value.trim().toLowerCase()
    if (!needle) return filtered
    return filtered.filter((doc) =>
      String(doc.analysis_model || '')
        .toLowerCase()
        .includes(needle),
    )
  })

  return { visibleDocuments }
}
