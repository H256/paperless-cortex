import { computed, reactive, ref } from 'vue'

export const useContinueProcessOptions = () => {
  const processOptions = reactive({
    includeSync: true,
    includeVisionOcr: true,
    includeEmbeddingsPaperless: true,
    includeEmbeddingsVision: true,
    embeddingsMode: 'auto' as 'auto' | 'paperless' | 'vision' | 'both',
    includePageNotes: true,
    includeHierarchicalSummary: true,
    includeSuggestionsPaperless: true,
    includeSuggestionsVision: true,
  })

  const batchOptions = [10, 20, 50, 100, 200, 500, 'All'] as const
  const batchIndex = ref(batchOptions.length - 1)
  const batchLimit = computed(() => {
    const value = batchOptions[batchIndex.value]
    return value === 'All' ? null : value
  })
  const batchLabel = computed(() => (batchLimit.value === null ? 'All' : String(batchLimit.value)))
  const includeEmbeddings = computed(
    () => processOptions.includeEmbeddingsPaperless || processOptions.includeEmbeddingsVision,
  )

  const processParams = () => ({
    include_sync: processOptions.includeSync,
    include_vision_ocr: processOptions.includeVisionOcr,
    include_embeddings: includeEmbeddings.value,
    include_embeddings_paperless: processOptions.includeEmbeddingsPaperless,
    include_embeddings_vision: processOptions.includeEmbeddingsVision,
    embeddings_mode: processOptions.embeddingsMode,
    include_page_notes: processOptions.includePageNotes,
    include_summary_hierarchical: processOptions.includeHierarchicalSummary,
    include_suggestions_paperless: processOptions.includeSuggestionsPaperless,
    include_suggestions_vision: processOptions.includeSuggestionsVision,
    limit: batchLimit.value ?? undefined,
  })

  return {
    processOptions,
    batchOptions,
    batchIndex,
    batchLimit,
    batchLabel,
    processParams,
  }
}
