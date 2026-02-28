import { watch } from 'vue'
import { useDocumentDetailCoreData } from './useDocumentDetailCoreData'
import { useDocumentSuggestions } from './useDocumentSuggestions'

export const useDocumentDetailData = () => {
  const core = useDocumentDetailCoreData()
  const suggestions = useDocumentSuggestions()

  watch(
    () => core.document.value?.id,
    () => {
      suggestions.resetSuggestionsState()
    },
  )

  return {
    ...core,
    ...suggestions,
  }
}
