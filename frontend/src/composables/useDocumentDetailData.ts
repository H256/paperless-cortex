import { watch } from 'vue'
import { useDocumentDetailCoreData } from './useDocumentDetailCoreData'
import { useDocumentSuggestions } from './useDocumentSuggestions'

export const useDocumentDetailData = () => {
  const core = useDocumentDetailCoreData()
  const suggestions = useDocumentSuggestions()

  const loadDocument = async (id: number) => {
    await core.loadDocument(id)
    suggestions.resetSuggestionsState()
  }

  watch(
    () => core.document.value?.id,
    () => {
      suggestions.resetSuggestionsState()
    },
  )

  return {
    ...core,
    loadDocument,
    ...suggestions,
  }
}
